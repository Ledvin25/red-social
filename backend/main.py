from flask import Flask, jsonify, request
import psycopg2
from psycopg2 import OperationalError
from pymongo import MongoClient
import redis
from tenacity import retry, wait_fixed, stop_after_delay

app = Flask(__name__)

# Reacciones válidas
REACTIONS = ["like", "love", "haha", "wow", "sad", "angry"]

X = 5  # Cantidad de reacciones para cachear un post

# Configuración de PostgreSQL con reintentos
@retry(wait=wait_fixed(2), stop=stop_after_delay(30))
def connect_to_postgres():
    return psycopg2.connect(
        dbname="mydatabase",
        user="myuser",
        password="mypassword",
        host="db"
    )

try:
    pg_conn = connect_to_postgres()
except OperationalError as e:
    print(f"Error connecting to PostgreSQL: {e}")

# Configuración de MongoDB
try:
    mongo_client = MongoClient("mongodb://mongo:27017/")
    mongo_db = mongo_client["mydatabase"]
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")

# Configuración de Redis
try:
    redis_client = redis.Redis(host='redis', port=6379, db=0)
except Exception as e:
    print(f"Error connecting to Redis: {e}")

# Token estático para autenticación básica temporal
STATIC_TOKEN = "SOYUNTOKEN"

# Middleware de autenticación
@app.before_request
def authenticate():
    if request.endpoint != 'login':
        token = request.headers.get('Authorization')
        if token != STATIC_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        

# --------------------------------------- USERS ---------------------------------------

# Signup
@app.route("/signup", methods=["POST"])
def signup():
    # Singup simple, solo se crea un user y contraseña en la base de datos y se guarda el sub en la base de datos
    # Ya que no se especifica en el enunciado como se autentica el usuario, se presumia hacerlo con OAuth2 pero por simplicidad se hace con un token estático

    # Obtener los datos del usuario
    username = request.form.get("username")
    password = request.form.get("password")

    # Validar que los datos requeridos estén presentes
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    
    # Insertar el usuario en la base de datos
    cursor = pg_conn.cursor()
    cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s) RETURNING sub", (username, password))
    user_id = cursor.fetchone()[0]
    pg_conn.commit()
    cursor.close()

    return jsonify({"message": "User created successfully", "sub": user_id})

# Login
@app.route("/login", methods=["POST"])
def login():
    # login simple, solo se verifica el usuario y contraseña en la base de datos
    # Ya que no se especifica en el enunciado como se autentica el usuario, se presumia hacerlo con OAuth2 pero por simplicidad se hace con un token estático

    # Obtener los datos del usuario
    username = request.form.get("username")
    password = request.form.get("password")

    # Validar que los datos requeridos estén presentes
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    
    # Verificar las credenciales en la base de datos
    cursor = pg_conn.cursor()
    cursor.execute("SELECT sub FROM users WHERE username = %s AND password = %s", (username, password))
    user_id = cursor.fetchone()
    cursor.close()

    if not user_id:
        return jsonify({"error": "Invalid credentials"}), 401
    
    
    # Guardar la sesión en Redis con un TTL de 10 horas (36000 segundos)
    session_id = "session_id_example"  # Aquí se generaría un ID de sesión único
    redis_client.setex(f"session:{session_id}", 36000, STATIC_TOKEN)
    
    return jsonify({"message": "Login successful", "token": STATIC_TOKEN, "session_id": session_id})

# Logout
@app.route("/logout", methods=["POST"])
def logout():
    # Eliminar la sesión de Redis
    session_id = request.headers.get('Session-ID')
    redis_client.delete(f"session:{session_id}")
    
    return jsonify({"message": "Logout successful"})

# Comprobar si el cookie es igual al de redis
@app.route("/check-session", methods=["POST"])
def check_session():
    # Comprobar si el cookie es igual al de Redis
    session_id = request.headers.get('Session-ID')
    token = redis_client.get(f"session:{session_id}")
    if token:
        # Reiniciar el TTL de 10 horas (36000 segundos)
        redis_client.expire(f"session:{session_id}", 36000)
        return jsonify({"message": "Session is valid"})
    else:
        return jsonify({"error": "Session is invalid"}), 401

# --------------------------------------- POSTS ---------------------------------------

# Obtener todos los posts
@app.route("/posts", methods=["GET"])
def get_posts():
    posts_collection = mongo_db["posts"]
    posts = list(posts_collection.find({}, {"_id": 0}))
    return jsonify(posts)

# Crear un nuevo post
@app.route("/posts", methods=["POST"])
def create_post():
    # Obtener los datos del post
    content = request.form.get("content")
    media = request.form.get("media")
    destinations = request.form.get("destinations")

    # Logica para convertir en lista media y destinations
    if media:
        media = media.split(",")
    if destinations:
        try:
            destinations = [int(dest_id) for dest_id in destinations.split(",")]  # Convertir la cadena de ids a una lista de enteros
        except ValueError:
            return jsonify({"error": "Invalid format for destinations"}), 400

    # Obtener el sub de usuario desde el token y el nombre de usuario desde la base de datos
    user_id = 1  # Aquí iría la lógica para obtener el sub de usuario desde el token
    cursor = pg_conn.cursor()
    cursor.execute("SELECT username FROM users WHERE sub = %s", (user_id,))
    userName = cursor.fetchone()[0]

    # Validar que los datos requeridos estén presentes
    if not content or not destinations or not media:
        return jsonify({"error": "Content, destinations, and media are required"}), 400

    # Validar que los destinos existan en MongoDB y obtener sus nombres
    destinations_collection = mongo_db["destinations"]
    valid_destinations = []
    for destination_id in destinations:
        db_destination = destinations_collection.find_one({"id": destination_id}, {"_id": 0, "name": 1})
        if not db_destination:
            return jsonify({"error": f"Destination with id {destination_id} not found"}), 404
        valid_destinations.append({"id": destination_id, "name": db_destination["name"]})

    # Insertar relacion en postgres
    cursor.execute("INSERT INTO posts (sub) VALUES (%s) RETURNING post_id", (user_id,))
    post_id = cursor.fetchone()[0]

    # Insertar post en MongoDB
    posts_collection = mongo_db["posts"]
    post = {
        "user_id": user_id,
        "id": post_id,
        "userName": userName,
        "content": content,
        "media": media,
        "destinations": valid_destinations,
        "reactions": [],
        "comments": []
    }

    posts_collection.insert_one(post)

    # Espacio por si se quiere agregar un cache en Redis

    pg_conn.commit()
    cursor.close()
    return jsonify({"message": "Post created successfully"})

# Editar un post (solo el usuario que lo creó)
@app.route("/posts/<int:post_id>", methods=["PUT"])
def edit_post(post_id):
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el post de MongoDB
    posts_collection = mongo_db["posts"]
    post = posts_collection.find_one({"id": post_id})
    if not post:
        return jsonify({"error": "Post not found"}), 404

    # Validar que el usuario sea el creador del post
    if post["user_id"] != user_id:
        return jsonify({"error": "Unauthorized"}), 401

    # Obtener los datos del post
    content = request.form.get("content")
    media = request.form.get("media")
    destinations = request.form.get("destinations")

    # Editar los campos del post
    if content:
        post["content"] = content + " (Editado)"
    if media:
        post["media"] = media.split(",")
    if destinations:
        try:
            post["destinations"] = [int(dest_id) for dest_id in destinations.split(",")]
        except ValueError:
            return jsonify({"error": "Invalid format for destinations"}), 400

    posts_collection.update_one({"id": post_id}, {"$set": post})
    return jsonify({"message": "Post edited successfully"})

# Eliminar un post (solo el usuario que lo creó)
@app.route("/posts/<int:post_id>", methods=["DELETE"])
def delete_post(post_id):
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el post de MongoDB
    posts_collection = mongo_db["posts"]
    post = posts_collection.find_one({"id": post_id})
    if not post:
        return jsonify({"error": "Post not found"}), 404

    # Validar que el usuario sea el creador del post
    if post["user_id"] != user_id:
        return jsonify({"error": "Unauthorized"}), 401

    # Eliminar el post
    posts_collection.delete_one({"id": post_id})
    return jsonify({"message": "Post deleted successfully"})


# --------------------------------------- REACTIONS ---------------------------------------

# Reaccionar a un post, comentario o destino
@app.route("/posts/<int:post_id>/reactions", methods=["POST"])
@app.route("/posts/<int:post_id>/comments/<int:comment_id>/reactions", methods=["POST"])
@app.route("/destinations/<int:destination_id>/reactions", methods=["POST"])
@app.route("/destinations/<int:destination_id>/comments/<int:comment_id>/reactions", methods=["POST"])
def react_to_post_comment_or_destination(post_id=None, comment_id=None, destination_id=None):
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el nombre de usuario desde la base de datos
    cursor = pg_conn.cursor()
    cursor.execute("SELECT username FROM users WHERE sub = %s", (user_id,))
    userName = cursor.fetchone()[0]

    # Validar que la reacción sea válida
    reaction = request.form.get("reaction")
    if reaction not in REACTIONS:
        return jsonify({"error": "Invalid reaction"}), 400

    if post_id is not None:
        # Obtener el post de MongoDB
        posts_collection = mongo_db["posts"]
        post = posts_collection.find_one({"id": post_id})
        if not post:
            return jsonify({"error": "Post not found"}), 404
        
        if comment_id is None:
            # Reaccionar a un post
            target = post
        else:
            # Reaccionar a un comentario de un post
            target = next((c for c in post["comments"] if c.get("comment_id") == comment_id), None)
            if not target:
                return jsonify({"error": "Comment not found"}), 404

    elif destination_id is not None:
        # Obtener el destino de MongoDB
        destinations_collection = mongo_db["destinations"]
        destination = destinations_collection.find_one({"id": destination_id})
        if not destination:
            return jsonify({"error": "Destination not found"}), 404
        
        if comment_id is None:
            # Reaccionar a un destino
            target = destination
        else:
            # Reaccionar a un comentario de un destino
            target = next((c for c in destination["comments"] if c.get("comment_id") == comment_id), None)
            if not target:
                return jsonify({"error": "Comment not found"}), 404

    # Verificar si el usuario ya ha reaccionado
    for user_reaction in target["reactions"]:
        if user_reaction.get("user_id") == user_id:
            if user_reaction["reaction"] == reaction:
                return jsonify({"error": "User has already reacted with the same reaction"}), 400
            else:
                # Eliminar la reacción anterior
                target["reactions"] = [r for r in target["reactions"] if r.get("user_id") != user_id]
                break
    
    # Insertar la nueva reacción
    target["reactions"].append({
        "user_id": user_id,
        "userName": userName,
        "reaction": reaction
    })

    if post_id is not None:
        posts_collection.update_one({"id": post_id}, {"$set": post})
    elif destination_id is not None:
        destinations_collection.update_one({"id": destination_id}, {"$set": destination})

    return jsonify({"message": "Reaction added successfully"})

# Eliminar reacción a un post, comentario o destino
@app.route("/posts/<int:post_id>/reactions", methods=["DELETE"])
@app.route("/posts/<int:post_id>/comments/<int:comment_id>/reactions", methods=["DELETE"])
@app.route("/destinations/<int:destination_id>/reactions", methods=["DELETE"])
@app.route("/destinations/<int:destination_id>/comments/<int:comment_id>/reactions", methods=["DELETE"])
def delete_reaction(post_id=None, comment_id=None, destination_id=None):
    # Obtener el sub de usuario desde el token
    user_id = 1

    if post_id is not None:
        # Obtener el post de MongoDB
        posts_collection = mongo_db["posts"]
        post = posts_collection.find_one({"id": post_id})
        if not post:
            return jsonify({"error": "Post not found"}), 404
        
        if comment_id is None:
            # Eliminar reacción de un post
            target = post
        else:
            # Eliminar reacción de un comentario de un post
            target = next((c for c in post["comments"] if c.get("comment_id") == comment_id), None)
            if not target:
                return jsonify({"error": "Comment not found"}), 404

    elif destination_id is not None:
        # Obtener el destino de MongoDB
        destinations_collection = mongo_db["destinations"]
        destination = destinations_collection.find_one({"id": destination_id})
        if not destination:
            return jsonify({"error": "Destination not found"}), 404
        
        if comment_id is None:
            # Eliminar reacción de un destino
            target = destination
        else:
            # Eliminar reacción de un comentario de un destino
            target = next((c for c in destination["comments"] if c.get("comment_id") == comment_id), None)
            if not target:
                return jsonify({"error": "Comment not found"}), 404

    # Eliminar reacción
    target["reactions"] = [reaction for reaction in target["reactions"] if reaction.get("user_id") != user_id]

    if post_id is not None:
        posts_collection.update_one({"id": post_id}, {"$set": post})
    elif destination_id is not None:
        destinations_collection.update_one({"id": destination_id}, {"$set": destination})

    return jsonify({"message": "Reaction deleted successfully"})

# --------------------------------------- COMMENTS ---------------------------------------

# Comentar un post o un destino
@app.route("/posts/<int:post_id>/comments", methods=["POST"])
@app.route("/destinations/<int:destination_id>/comments", methods=["POST"])
def comment_on_post_or_destination(post_id=None, destination_id=None):
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el nombre de usuario desde la base de datos
    cursor = pg_conn.cursor()
    cursor.execute("SELECT username FROM users WHERE sub = %s", (user_id,))
    userName = cursor.fetchone()[0]

    if post_id is not None:
        # Obtener el post de MongoDB
        posts_collection = mongo_db["posts"]
        post = posts_collection.find_one({"id": post_id})
        if not post:
            return jsonify({"error": "Post not found"}), 404
        
        # Obtener el comentario
        comment = request.form.get("comment")
        if not comment:
            return jsonify({"error": "Comment is required"}), 400
        
        # Generar un comment_id único
        comment_id = len(post["comments"]) + 1

        # Insertar el comentario en el post
        post["comments"].append({
            "comment_id": comment_id,
            "user_id": user_id,
            "userName": userName,
            "comment": comment,
            "reactions": []
        })

        posts_collection.update_one({"id": post_id}, {"$set": post})
        return jsonify({"message": "Comment added successfully"})

    elif destination_id is not None:
        # Obtener el destino de MongoDB
        destinations_collection = mongo_db["destinations"]
        destination = destinations_collection.find_one({"id": destination_id})
        if not destination:
            return jsonify({"error": "Destination not found"}), 404
        
        # Obtener el comentario
        comment = request.form.get("comment")
        if not comment:
            return jsonify({"error": "Comment is required"}), 400
        
        # Generar un comment_id único
        comment_id = len(destination["comments"]) + 1

        # Insertar el comentario en el destino
        destination["comments"].append({
            "comment_id": comment_id,
            "user_id": user_id,
            "userName": userName,
            "comment": comment,
            "reactions": []
        })

        destinations_collection.update_one({"id": destination_id}, {"$set": destination})
        return jsonify({"message": "Comment added successfully"})

# Editar un comentario en un post o un destino
@app.route("/posts/<int:post_id>/comments/<int:comment_id>", methods=["PUT"])
@app.route("/destinations/<int:destination_id>/comments/<int:comment_id>", methods=["PUT"])
def edit_comment(post_id=None, destination_id=None, comment_id=None):
    # Obtener el sub de usuario desde el token
    user_id = 1

    if post_id is not None:
        # Obtener el post de MongoDB
        posts_collection = mongo_db["posts"]
        post = posts_collection.find_one({"id": post_id})
        if not post:
            return jsonify({"error": "Post not found"}), 404
        
        # Buscar el comentario
        comment = next((c for c in post["comments"] if c.get("comment_id") == comment_id and c.get("user_id") == user_id), None)
        if not comment:
            return jsonify({"error": "Comment not found"}), 404

        # Editar el comentario
        new_comment = request.form.get("comment")
        if not new_comment:
            return jsonify({"error": "Comment is required"}), 400
        
        comment["comment"] = new_comment + " (Editado)"
        posts_collection.update_one({"id": post_id}, {"$set": post})
        return jsonify({"message": "Comment edited successfully"})

    elif destination_id is not None:
        # Obtener el destino de MongoDB
        destinations_collection = mongo_db["destinations"]
        destination = destinations_collection.find_one({"id": destination_id})
        if not destination:
            return jsonify({"error": "Destination not found"}), 404
        
        # Buscar el comentario
        comment = next((c for c in destination["comments"] if c.get("comment_id") == comment_id and c.get("user_id") == user_id), None)
        if not comment:
            return jsonify({"error": "Comment not found"}), 404

        # Editar el comentario
        new_comment = request.form.get("comment")
        if not new_comment:
            return jsonify({"error": "Comment is required"}), 400
        
        comment["comment"] = new_comment + " (Editado)"
        destinations_collection.update_one({"id": destination_id}, {"$set": destination})
        return jsonify({"message": "Comment edited successfully"})

# Eliminar un comentario de un post o un destino
@app.route("/posts/<int:post_id>/comments/<int:comment_id>", methods=["DELETE"])
@app.route("/destinations/<int:destination_id>/comments/<int:comment_id>", methods=["DELETE"])
def delete_comment(post_id=None, destination_id=None, comment_id=None):
    # Obtener el sub de usuario desde el token
    user_id = 1

    if post_id is not None:
        # Obtener el post de MongoDB
        posts_collection = mongo_db["posts"]
        post = posts_collection.find_one({"id": post_id})
        if not post:
            return jsonify({"error": "Post not found"}), 404
        
        # Buscar el comentario
        comment = next((c for c in post["comments"] if c.get("comment_id") == comment_id and c.get("user_id") == user_id), None)
        if not comment:
            return jsonify({"error": "Comment not found"}), 404
        
        # Eliminar el comentario
        post["comments"] = [c for c in post["comments"] if c.get("comment_id") != comment_id]
        posts_collection.update_one({"id": post_id}, {"$set": post})
        return jsonify({"message": "Comment deleted successfully"})

    elif destination_id is not None:
        # Obtener el destino de MongoDB
        destinations_collection = mongo_db["destinations"]
        destination = destinations_collection.find_one({"id": destination_id})
        if not destination:
            return jsonify({"error": "Destination not found"}), 404
        
        # Buscar el comentario
        comment = next((c for c in destination["comments"] if c.get("comment_id") == comment_id and c.get("user_id") == user_id), None)
        if not comment:
            return jsonify({"error": "Comment not found"}), 404
        
        # Eliminar el comentario
        destination["comments"] = [c for c in destination["comments"] if c.get("comment_id") != comment_id]
        destinations_collection.update_one({"id": destination_id}, {"$set": destination})
        return jsonify({"message": "Comment deleted successfully"})

# --------------------------------------- DESTINATIONS ---------------------------------------

# Obtener destinos
@app.route("/destinations", methods=["GET"])
def get_destinations():
    destinations_collection = mongo_db["destinations"]
    destinations = list(destinations_collection.find({}, {"_id": 0}))
    return jsonify(destinations)

# Agregar un destino
@app.route("/destinations", methods=["POST"])
def add_destination():
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el nombre de usuario desde la base de datos
    cursor = pg_conn.cursor()
    cursor.execute("SELECT username FROM users WHERE sub = %s", (user_id,))
    userName = cursor.fetchone()[0]

    # Obtener los datos del destino
    name = request.form.get("name")
    description = request.form.get("description")
    city = request.form.get("city")
    country = request.form.get("country")
    media = request.form.get("media")

    # Validar que los datos requeridos estén presentes
    if not name or not description or not city or not country or not media:
        return jsonify({"error": "All fields are required"}), 400

    # Verificar que el nombre del destino sea único
    destinations_collection = mongo_db["destinations"]
    if destinations_collection.find_one({"name": name}):
        return jsonify({"error": "Destination name must be unique"}), 400

    # Logica para convertir en lista media
    media = media.split(",")

    # Generar un id único para el destino
    last_destination = destinations_collection.find_one(sort=[("id", -1)])
    destination_id = last_destination["id"] + 1 if last_destination else 1

    # Crear el destino
    destination = {
        "id": destination_id,
        "user_id": user_id,
        "userName": userName,
        "name": name,
        "description": description,
        "city": city,
        "country": country,
        "media": media,
        "comments": [],
        "reactions": []
    }

    # Insertar el destino en MongoDB
    destinations_collection.insert_one(destination)
    return jsonify({"message": "Destination added successfully"})

# Editar un destino (solo el usuario que lo creó)
@app.route("/destinations/<int:destination_id>", methods=["PUT"])
def edit_destination(destination_id):
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el destino de MongoDB
    destinations_collection = mongo_db["destinations"]
    destination = destinations_collection.find_one({"id": destination_id})
    if not destination:
        return jsonify({"error": "Destination not found"}), 404

    # Validar que el usuario sea el creador del destino
    if destination["user_id"] != user_id:
        return jsonify({"error": "Unauthorized"}), 401

    # Obtener los datos del destino
    name = request.form.get("name")
    description = request.form.get("description")
    city = request.form.get("city")
    country = request.form.get("country")
    media = request.form.get("media")

    # Editar los campos del destino
    if name:
        destination["name"] = name
    if description:
        destination["description"] = description
    if city:
        destination["city"] = city
    if country:
        destination["country"] = country
    if media:
        destination["media"] = media.split(",")

    destinations_collection.update_one({"id": destination_id}, {"$set": destination})
    return jsonify({"message": "Destination edited successfully"})

# Eliminar un destino (solo el usuario que lo creó)
@app.route("/destinations/<int:destination_id>", methods=["DELETE"])
def delete_destination(destination_id):
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el destino de MongoDB
    destinations_collection = mongo_db["destinations"]
    destination = destinations_collection.find_one({"id": destination_id})
    if not destination:
        return jsonify({"error": "Destination not found"}), 404

    # Validar que el usuario sea el creador del destino
    if destination["user_id"] != user_id:
        return jsonify({"error": "Unauthorized"}), 401

    # Eliminar el destino
    destinations_collection.delete_one({"id": destination_id})
    return jsonify({"message": "Destination deleted successfully"})

# --------------------------------------- TripGoals ---------------------------------------

# Obtener los trip goals de un usuario
@app.route("/trip-goals/<int:user_id>", methods=["GET"])
def get_trip_goals(user_id):
    # Obtener el nombre de usuario desde la base de datos
    cursor = pg_conn.cursor()
    cursor.execute("SELECT username FROM users WHERE sub = %s", (user_id,))
    userName = cursor.fetchone()[0]

    # Obtener los trip goals del usuario desde MongoDB
    trip_goals_collection = mongo_db["tripGoals"]
    trip_goals = trip_goals_collection.find_one({"user_id": user_id}, {"_id": 0})

    if not trip_goals:
        return jsonify({"error": "Trip goals not found"}), 404

    return jsonify(trip_goals)
    
# Agregar un trip goal al usuario actual
@app.route("/trip-goals", methods=["POST"])
def add_trip_goal():
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el nombre de usuario desde la base de datos
    cursor = pg_conn.cursor()
    cursor.execute("SELECT username FROM users WHERE sub = %s", (user_id,))
    userName = cursor.fetchone()[0]

    # Obtener los datos del trip goal
    destination_ids = request.form.get("destination_ids")
    if not destination_ids:
        return jsonify({"error": "Destination IDs are required"}), 400

    try:
        destination_ids = [int(dest_id) for dest_id in destination_ids.split(",")]
    except ValueError:
        return jsonify({"error": "Invalid format for destination IDs"}), 400

    # Validar que los destinos existan en MongoDB y obtener sus nombres
    destinations_collection = mongo_db["destinations"]
    destinations = []
    for destination_id in destination_ids:
        db_destination = destinations_collection.find_one({"id": destination_id}, {"_id": 0, "name": 1})
        if not db_destination:
            return jsonify({"error": f"Destination with id {destination_id} not found"}), 404
        destinations.append({"id": destination_id, "name": db_destination["name"]})

    # Obtener la colección de trip goals
    trip_goals_collection = mongo_db["tripGoals"]

    # Generar un id único para el trip goal
    last_trip_goal = trip_goals_collection.find_one(sort=[("id", -1)])
    trip_goal_id = last_trip_goal["id"] + 1 if last_trip_goal else 1

    # Crear el trip goal
    trip_goal = {
        "id": trip_goal_id,
        "userName": userName,
        "user_id": user_id,
        "destinations": destinations,
        "followers": []
    }

    # Insertar el trip goal en MongoDB
    trip_goals_collection.insert_one(trip_goal)
    return jsonify({"message": "Trip goal added successfully"})

# Editar un trip goal (solo el usuario que lo creó)
@app.route("/trip-goals/<int:trip_goal_id>", methods=["PUT"])
def edit_trip_goal(trip_goal_id):
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el trip goal de MongoDB
    trip_goals_collection = mongo_db["tripGoals"]
    trip_goal = trip_goals_collection.find_one({"id": trip_goal_id})
    if not trip_goal:
        return jsonify({"error": "Trip goal not found"}), 404

    # Validar que el usuario sea el creador del trip goal
    if trip_goal["user_id"] != user_id:
        return jsonify({"error": "Unauthorized"}), 401

    # Obtener los datos del trip goal
    destination_ids = request.form.get("destination_ids")
    if not destination_ids:
        return jsonify({"error": "Destination IDs are required"}), 400

    try:
        destination_ids = [int(dest_id) for dest_id in destination_ids.split(",")]
    except ValueError:
        return jsonify({"error": "Invalid format for destination IDs"}), 400

    # Validar que los destinos existan en MongoDB y obtener sus nombres
    destinations_collection = mongo_db["destinations"]
    destinations = []
    for destination_id in destination_ids:
        db_destination = destinations_collection.find_one({"id": destination_id}, {"_id": 0, "name": 1})
        if not db_destination:
            return jsonify({"error": f"Destination with id {destination_id} not found"}), 404
        destinations.append({"id": destination_id, "name": db_destination["name"]})

    # Editar los destinos del trip goal
    trip_goal["destinations"] = destinations

    trip_goals_collection.update_one({"id": trip_goal_id}, {"$set": trip_goal})
    return jsonify({"message": "Trip goal edited successfully"})

# Eliminar un trip goal (solo el usuario que lo creó)
@app.route("/trip-goals/<int:trip_goal_id>", methods=["DELETE"])
def delete_trip_goal(trip_goal_id):
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el trip goal de MongoDB
    trip_goals_collection = mongo_db["tripGoals"]
    trip_goal = trip_goals_collection.find_one({"id": trip_goal_id})
    if not trip_goal:
        return jsonify({"error": "Trip goal not found"}), 404

    # Validar que el usuario sea el creador del trip goal
    if trip_goal["user_id"] != user_id:
        return jsonify({"error": "Unauthorized"}), 401

    # Eliminar el trip goal
    trip_goals_collection.delete_one({"id": trip_goal_id})
    return jsonify({"message": "Trip goal deleted successfully"})

# Seguir un trip goal
@app.route("/trip-goals/<int:trip_goal_id>/follow", methods=["POST"])
def follow_trip_goal(trip_goal_id):
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el nombre de usuario desde la base de datos
    cursor = pg_conn.cursor()
    cursor.execute("SELECT username FROM users WHERE sub = %s", (user_id,))
    userName = cursor.fetchone()[0]

    # Obtener el trip goal de MongoDB
    trip_goals_collection = mongo_db["tripGoals"]
    trip_goal = trip_goals_collection.find_one({"id": trip_goal_id})
    if not trip_goal:
        return jsonify({"error": "Trip goal not found"}), 404

    # Verificar si el usuario ya sigue el trip goal
    if next((f for f in trip_goal["followers"] if f.get("user_id") == user_id), None):
        return jsonify({"error": "User already follows this trip goal"}), 400

    # Seguir el trip goal
    trip_goal["followers"].append({
        "user_id": user_id,
        "userName": userName
    })

    trip_goals_collection.update_one({"id": trip_goal_id}, {"$set": trip_goal})

    # Insertar en la tabla de PostgreSQL
    cursor.execute(
        "INSERT INTO trip_goals (trip_goal_id, sub) VALUES (%s, %s)",
        (trip_goal_id, user_id)
    )
    pg_conn.commit()
    cursor.close()

    return jsonify({"message": "Trip goal followed successfully"})

# Dejar de seguir un trip goal
@app.route("/trip-goals/<int:trip_goal_id>/unfollow", methods=["POST"])
def unfollow_trip_goal(trip_goal_id):
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener el trip goal de MongoDB
    trip_goals_collection = mongo_db["tripGoals"]
    trip_goal = trip_goals_collection.find_one({"id": trip_goal_id})
    if not trip_goal:
        return jsonify({"error": "Trip goal not found"}), 404

    # Verificar si el usuario sigue el trip goal
    follower = next((f for f in trip_goal["followers"] if f.get("user_id") == user_id), None)
    if not follower:
        return jsonify({"error": "User does not follow this trip goal"}), 400

    # Dejar de seguir el trip goal
    trip_goal["followers"] = [f for f in trip_goal["followers"] if f.get("user_id") != user_id]

    trip_goals_collection.update_one({"id": trip_goal_id}, {"$set": trip_goal})

    # Eliminar de la tabla de PostgreSQL
    cursor = pg_conn.cursor()
    cursor.execute(
        "DELETE FROM trip_goals WHERE trip_goal_id = %s AND sub = %s",
        (trip_goal_id, user_id)
    )
    pg_conn.commit()
    cursor.close()

    return jsonify({"message": "Trip goal unfollowed successfully"})

# Obtener los trip goals seguidos por un usuario
@app.route("/trip-goals/followed", methods=["GET"])
def get_followed_trip_goals():
    # Obtener el sub de usuario desde el token
    user_id = 1

    # Obtener los trip goals seguidos por el usuario desde PostgreSQL
    cursor = pg_conn.cursor()
    cursor.execute(
        "SELECT trip_goal_id FROM trip_goals WHERE sub = %s",
        (user_id,)
    )
    followed_trip_goals = cursor.fetchall()

    # Obtener los trip goals de MongoDB
    trip_goals_collection = mongo_db["tripGoals"]
    trip_goals = trip_goals_collection.find({"id": {"$in": [t[0] for t in followed_trip_goals]}}, {"_id": 0})

    return jsonify(list(trip_goals))

# Esto se estaría ejecutando en un worker o en un cronjob cada cierto tiempo
# Cachear los posts con mas de x reacciones en Redis
@app.route("/cache-posts", methods=["POST"])
def cache_posts():
    # Obtener los posts con más de X reacciones
    posts_collection = mongo_db["posts"]
    posts = list(posts_collection.find({}, {"_id": 0}))
    popular_posts = [post for post in posts if len(post["reactions"]) >= X]

    # Insertar los posts en Redis con un TTL de un día (86400 segundos)
    for post in popular_posts:
        redis_client.setex(f"post:{post['id']}", 86400, post)

    return jsonify({"message": "Posts cached successfully"})

# --------------------------------------- ENDPOINTS ADICIONALES ---------------------------------------

# El enunciado no especifica si se debe implementar un endpoint para obtener un especifico post, comentario, destino, etc. 
# Pero aqui se muestra un ejemplo de como se podria hacer, aplica para todos los modelos, primero se busca en Redis y si no se encuentra se busca en MongoDB.

# Obtener un post
@app.route("/posts/<int:post_id>", methods=["GET"])
def get_post(post_id):
    # Obtener el post de Redis
    post = redis_client.get(f"post:{post_id}")
    if post:
        return jsonify(post)
    
    # Obtener el post de MongoDB
    posts_collection = mongo_db["posts"]
    post = posts_collection.find_one({"id": post_id}, {"_id": 0})
    if not post:
        return jsonify({"error": "Post not found"}), 404

    return jsonify(post)

# --------------------------------------- MAIN ---------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
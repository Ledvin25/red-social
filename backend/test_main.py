import pytest
from flask import Flask, request, jsonify
from main import app, pg_conn, mongo_db, redis_client, STATIC_TOKEN
import time

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

# Retry mechanism to ensure PostgreSQL is ready
def wait_for_postgres():
    retries = 5
    while retries > 0:
        try:
            pg_conn.cursor().execute('SELECT 1')
            return
        except Exception as e:
            print(f"Waiting for PostgreSQL to be ready: {e}")
            retries -= 1
            time.sleep(5)
    raise Exception("PostgreSQL is not ready")

@pytest.fixture(autouse=True)
def setup_and_teardown():
    wait_for_postgres()
    yield
    # Teardown code if needed

# 1- Test successful signup
def test_signup(client):
    response = client.post('/signup', data={ "username": "test", "password": "test" })
    assert response.status_code == 200
    assert response.json == { "message": "User created successfully" }

# 2- Test unsuccessful signup
def test_signup_fail(client):
    response = client.post('/signup', data={ "username": "test", "password": "" })
    assert response.status_code == 400
    assert response.json == { "error": "Username and password are required"}

# 3- Test successful login
def test_login(client):
    # First, create a user to login with
    client.post('/signup', data={ "username": "test", "password": "test" })
        
    response = client.post('/login', data={ "username": "test", "password": "test" })
    assert response.status_code == 200
    assert response.json["message"] == "Login successful"
    assert "token" in response.json
    assert "session_id" in response.json

# 4- Test unsuccessful login with missing credentials
def test_login_missing_credentials(client):
    response = client.post('/login', data={ "username": "test", "password": "" })
    assert response.status_code == 400
    assert response.json == { "error": "Username and password are required" }

# 5- Test unsuccessful login with invalid credentials
def test_login_invalid_credentials(client):
    response = client.post('/login', data={ "username": "invalid", "password": "invalid" })
    assert response.status_code == 401
    assert response.json == { "error": "Invalid credentials" }

# 6- Test successful logout
def test_logout(client):    
    # Login
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Logout
    response = client.post('/logout', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Logout successful" }

# 7- Test unsuccessful logout with missing headers
def test_logout_missing_headers(client):
    response = client.post('/logout')
    assert response.status_code == 401
    assert response.json == { "error": "Unauthorized" }

# 8- Test successful session check
def test_check_session(client):
    # Login
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Check session
    response = client.post('/check-session', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Session is valid" }

# 9- Test unsuccessful session check with invalid session
def test_check_session_invalid(client):
    # Check session with invalid session ID
    response = client.post('/check-session', headers={ "Authorization": STATIC_TOKEN, "Session-ID": "invalid_session_id" })
    assert response.status_code == 401
    assert response.json == { "error": "Session is invalid" }

# 10- Test unsuccessful session check with missing session ID
def test_check_session_missing_session_id(client):
    # Check session without session ID
    response = client.post('/check-session', headers={ "Authorization": STATIC_TOKEN })
    assert response.status_code == 400
    assert response.json == { "error": "Session-ID is required" }

# 11- Test get all posts
def test_get_posts(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Insert some posts into the database
    mongo_db["posts"].insert_many([
        {"title": "Post 1", "content": "Content 1"},
        {"title": "Post 2", "content": "Content 2"}
    ])

    # Get all posts
    response = client.get('/posts', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert len(response.json) == 2
    assert response.json[0]["title"] == "Post 1"
    assert response.json[1]["title"] == "Post 2"

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
# 12- Test successful post creation
def test_create_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert some destinations into the database
    mongo_db["destinations"].insert_many([
        {"id": 1, "name": "Destination 1"},
        {"id": 2, "name": "Destination 2"}
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Create a new post
    response = client.post('/posts', data={
        "content": "This is a test post",
        "media": "image1.jpg,image2.jpg",
        "destinations": "1,2"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Post created successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 13- Test post creation with missing fields
def test_create_post_missing_fields(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Create a new post with missing fields
    response = client.post('/posts', data={
        "content": "This is a test post",
        "media": "image1.jpg,image2.jpg"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Content, destinations, and media are required" }

# 14- Test post creation with invalid destination format
def test_create_post_invalid_destination_format(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Create a new post with invalid destination format
    response = client.post('/posts', data={
        "content": "This is a test post",
        "media": "image1.jpg,image2.jpg",
        "destinations": "invalid_format"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Invalid format for destinations" }

# 15- Test post creation with non-existent destination
def test_create_post_non_existent_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Create a new post with non-existent destination
    response = client.post('/posts', data={
        "content": "This is a test post",
        "media": "image1.jpg,image2.jpg",
        "destinations": "999"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Destination with id 999 not found" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})
# 16- Test successful post edit
def test_edit_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert some destinations into the database
    mongo_db["destinations"].insert_many([
        {"id": 1, "name": "Destination 1"},
        {"id": 2, "name": "Destination 2"}
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Create a new post
    create_response = client.post('/posts', data={
        "content": "This is a test post",
        "media": "image1.jpg,image2.jpg",
        "destinations": "1,2"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert create_response.status_code == 200

    # Get the post ID by fetching the latest post
    posts_response = client.get('/posts', headers={ "Authorization": token, "Session-ID": session_id })
    assert posts_response.status_code == 200
    post_id = posts_response.json[-1]["id"]

    # Edit the post
    response = client.put(f'/posts/{post_id}', data={
        "content": "This is an edited test post",
        "media": "image3.jpg,image4.jpg",
        "destinations": "2"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Post edited successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 17- Test post edit with non-existent post
def test_edit_post_non_existent(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit a non-existent post
    response = client.put('/posts/999', data={
        "content": "This is an edited test post",
        "media": "image3.jpg,image4.jpg",
        "destinations": "2"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Post not found" }

# 18- Test post edit by unauthorized user
def test_edit_unauthorized_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert some destinations into the database
    mongo_db["destinations"].insert_many([
        {"id": 1, "name": "Destination 1"},
        {"id": 2, "name": "Destination 2"}
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Insert a new post manually
    mongo_db["posts"].insert_one({
        "user_id": 2,
        "id": 1,
        "userName": "User2",
        "content": "Texto de la publicación...",
        "media": ["image_link_1", "image_link_2"],
        "destinations": [
            {
                "id": 1,
                "name": "París",
            }
        ],
        "reactions": [
            {
                "user_id": 2,
                "userName": "User2",
                "reaction": "like",
            }
        ],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 2,
                "userName": "User2",
                "comment": "Gran publicación!",
                "reactions": [
                    {
                        "user_id": 3,
                        "userName": "User3",
                        "reaction": "like",
                    }
                ],
                "created_at": "2024-10-12T10:00:00Z"
            }
        ],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Get the post ID by fetching the latest post
    posts_response = client.get('/posts', headers={ "Authorization": token, "Session-ID": session_id })
    assert posts_response.status_code == 200
    post_id = posts_response.json[-1]["id"]

    # Edit the post
    response = client.put(f'/posts/{post_id}', data={
        "content": "This is an edited test post",
        "media": "image3.jpg,image4.jpg",
        "destinations": "2"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 401
    assert response.json == { "error": "Unauthorized" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 19- Test post edit with invalid destination format
def test_edit_post_invalid_destination_format(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert some destinations into the database
    mongo_db["destinations"].insert_many([
        {"id": 1, "name": "Destination 1"},
        {"id": 2, "name": "Destination 2"}
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Insert a new post manually
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Get the post ID by fetching the latest post
    posts_response = client.get('/posts', headers={ "Authorization": token, "Session-ID": session_id })
    assert posts_response.status_code == 200
    post_id = posts_response.json[-1]["id"]

    # Edit the post with invalid destination format
    response = client.put(f'/posts/{post_id}', data={
        "content": "This is an edited test post",
        "media": "image3.jpg,image4.jpg",
        "destinations": "invalid_format"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Invalid format for destinations" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 20- Test successful post deletion
def test_delete_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert some destinations into the database
    mongo_db["destinations"].insert_many([
        {"id": 1, "name": "Destination 1"},
        {"id": 2, "name": "Destination 2"}
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Create a new post
    create_response = client.post('/posts', data={
        "content": "This is a test post",
        "media": "image1.jpg,image2.jpg",
        "destinations": "1,2"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert create_response.status_code == 200

    # Get the post ID by fetching the latest post
    posts_response = client.get('/posts', headers={ "Authorization": token, "Session-ID": session_id })
    assert posts_response.status_code == 200
    post_id = posts_response.json[-1]["id"]

    # Delete the post
    response = client.delete(f'/posts/{post_id}', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Post deleted successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 21- Test post deletion with non-existent post
def test_delete_post_non_existent(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete a non-existent post
    response = client.delete('/posts/999', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Post not found" }

# 22- Test post deletion by unauthorized user
def test_delete_unauthorized_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert some destinations into the database
    mongo_db["destinations"].insert_many([
        {"id": 1, "name": "Destination 1"},
        {"id": 2, "name": "Destination 2"}
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Insert a new post manually
    mongo_db["posts"].insert_one({
        "user_id": 2,
        "id": 1,
        "userName": "User2",
        "content": "Texto de la publicación...",
        "media": ["image_link_1", "image_link_2"],
        "destinations": [
            {
                "id": 1,
                "name": "París",
            }
        ],
        "reactions": [
            {
                "user_id": 2,
                "userName": "User2",
                "reaction": "like",
            }
        ],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 2,
                "userName": "User2",
                "comment": "Gran publicación!",
                "reactions": [
                    {
                        "user_id": 3,
                        "userName": "User3",
                        "reaction": "like",
                    }
                ],
                "created_at": "2024-10-12T10:00:00Z"
            }
        ],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Get the post ID by fetching the latest post
    posts_response = client.get('/posts', headers={ "Authorization": token, "Session-ID": session_id })
    assert posts_response.status_code == 200
    post_id = posts_response.json[-1]["id"]

    # Delete the post
    response = client.delete(f'/posts/{post_id}', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 401
    assert response.json == { "error": "Unauthorized" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})


# 23- Test successful reaction to a post
def test_react_to_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # React to the post
    response = client.post('/posts/1/reactions', data={ "reaction": "like" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Reaction added successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 24- Test reaction to a non-existent post
def test_react_to_non_existent_post(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # React to a non-existent post
    response = client.post('/posts/999/reactions', data={ "reaction": "like" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Post not found" }

# 25- Test reaction to a post with invalid reaction
def test_react_to_post_invalid_reaction(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # React to the post with invalid reaction
    response = client.post('/posts/1/reactions', data={ "reaction": "invalid_reaction" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Invalid reaction" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 26- Test successful reaction to a comment on a post
def test_react_to_comment_on_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post with a comment into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 1,
                "userName": "test",
                "comment": "This is a test comment",
                "reactions": []
            }
        ],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # React to the comment on the post
    response = client.post('/posts/1/comments/1/reactions', data={ "reaction": "like" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Reaction added successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 27- Test reaction to a non-existent comment on a post
def test_react_to_non_existent_comment_on_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # React to a non-existent comment on the post
    response = client.post('/posts/1/comments/999/reactions', data={ "reaction": "like" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Comment not found" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 28- Test successful reaction to a destination
def test_react_to_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # React to the destination
    response = client.post('/destinations/1/reactions', data={ "reaction": "like" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Reaction added successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 29- Test reaction to a non-existent destination
def test_react_to_non_existent_destination(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # React to a non-existent destination
    response = client.post('/destinations/999/reactions', data={ "reaction": "like" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Destination not found" }

# 30- Test successful reaction to a comment on a destination
def test_react_to_comment_on_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination with a comment into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 1,
                "userName": "test",
                "comment": "This is a test comment",
                "reactions": []
            }
        ],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # React to the comment on the destination
    response = client.post('/destinations/1/comments/1/reactions', data={ "reaction": "like" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Reaction added successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 31- Test reaction to a non-existent comment on a destination
def test_react_to_non_existent_comment_on_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # React to a non-existent comment on the destination
    response = client.post('/destinations/1/comments/999/reactions', data={ "reaction": "like" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Comment not found" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})
# 32- Test successful reaction deletion from a post
def test_delete_reaction_from_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post with a reaction into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [
            {
                "user_id": 1,
                "userName": "test",
                "reaction": "like"
            }
        ],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the reaction from the post
    response = client.delete('/posts/1/reactions', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Reaction deleted successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 33- Test reaction deletion from a non-existent post
def test_delete_reaction_from_non_existent_post(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the reaction from a non-existent post
    response = client.delete('/posts/999/reactions', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Post not found" }

# 34- Test successful reaction deletion from a comment on a post
def test_delete_reaction_from_comment_on_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post with a comment and a reaction into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 1,
                "userName": "test",
                "comment": "This is a test comment",
                "reactions": [
                    {
                        "user_id": 1,
                        "userName": "test",
                        "reaction": "like"
                    }
                ]
            }
        ],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the reaction from the comment on the post
    response = client.delete('/posts/1/comments/1/reactions', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Reaction deleted successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 35- Test reaction deletion from a non-existent comment on a post
def test_delete_reaction_from_non_existent_comment_on_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the reaction from a non-existent comment on the post
    response = client.delete('/posts/1/comments/999/reactions', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Comment not found" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 36- Test successful reaction deletion from a destination
def test_delete_reaction_from_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination with a reaction into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [
            {
                "user_id": 1,
                "userName": "test",
                "reaction": "like"
            }
        ],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the reaction from the destination
    response = client.delete('/destinations/1/reactions', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Reaction deleted successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 37- Test reaction deletion from a non-existent destination
def test_delete_reaction_from_non_existent_destination(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the reaction from a non-existent destination
    response = client.delete('/destinations/999/reactions', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Destination not found" }

# 38- Test successful reaction deletion from a comment on a destination
def test_delete_reaction_from_comment_on_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination with a comment and a reaction into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 1,
                "userName": "test",
                "comment": "This is a test comment",
                "reactions": [
                    {
                        "user_id": 1,
                        "userName": "test",
                        "reaction": "like"
                    }
                ]
            }
        ],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the reaction from the comment on the destination
    response = client.delete('/destinations/1/comments/1/reactions', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Reaction deleted successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 39- Test reaction deletion from a non-existent comment on a destination
def test_delete_reaction_from_non_existent_comment_on_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the reaction from a non-existent comment on the destination
    response = client.delete('/destinations/1/comments/999/reactions', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Comment not found" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 40- Test successful comment on a post
def test_comment_on_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Comment on the post
    response = client.post('/posts/1/comments', data={ "comment": "This is a test comment" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Comment added successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 41- Test comment on a non-existent post
def test_comment_on_non_existent_post(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Comment on a non-existent post
    response = client.post('/posts/999/comments', data={ "comment": "This is a test comment" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Post not found" }

# 42- Test comment on a post with missing comment
def test_comment_on_post_missing_comment(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Comment on the post with missing comment
    response = client.post('/posts/1/comments', data={}, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Comment is required" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 43- Test successful comment on a destination
def test_comment_on_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Comment on the destination
    response = client.post('/destinations/1/comments', data={ "comment": "This is a test comment" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Comment added successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 44- Test comment on a non-existent destination
def test_comment_on_non_existent_destination(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Comment on a non-existent destination
    response = client.post('/destinations/999/comments', data={ "comment": "This is a test comment" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Destination not found" }

# 45- Test comment on a destination with missing comment
def test_comment_on_destination_missing_comment(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Comment on the destination with missing comment
    response = client.post('/destinations/1/comments', data={}, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Comment is required" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 46- Test successful comment edit on a post
def test_edit_comment_on_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post with a comment into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 1,
                "userName": "test",
                "comment": "This is a test comment",
                "reactions": []
            }
        ],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the comment on the post
    response = client.put('/posts/1/comments/1', data={ "comment": "This is an edited test comment" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Comment edited successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 47- Test comment edit on a non-existent post
def test_edit_comment_on_non_existent_post(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the comment on a non-existent post
    response = client.put('/posts/999/comments/1', data={ "comment": "This is an edited test comment" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Post not found" }

# 48- Test comment edit on a post with missing comment
def test_edit_comment_on_post_missing_comment(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post with a comment into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 1,
                "userName": "test",
                "comment": "This is a test comment",
                "reactions": []
            }
        ],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the comment on the post with missing comment
    response = client.put('/posts/1/comments/1', data={}, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Comment is required" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 49- Test successful comment edit on a destination
def test_edit_comment_on_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination with a comment into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 1,
                "userName": "test",
                "comment": "This is a test comment",
                "reactions": []
            }
        ],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the comment on the destination
    response = client.put('/destinations/1/comments/1', data={ "comment": "This is an edited test comment" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Comment edited successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 50- Test comment edit on a non-existent destination
def test_edit_comment_on_non_existent_destination(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the comment on a non-existent destination
    response = client.put('/destinations/999/comments/1', data={ "comment": "This is an edited test comment" }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Destination not found" }

# 51- Test comment edit on a destination with missing comment
def test_edit_comment_on_destination_missing_comment(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination with a comment into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 1,
                "userName": "test",
                "comment": "This is a test comment",
                "reactions": []
            }
        ],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the comment on the destination with missing comment
    response = client.put('/destinations/1/comments/1', data={}, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Comment is required" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 52- Test successful comment deletion from a post
def test_delete_comment_from_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post with a comment into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 1,
                "userName": "test",
                "comment": "This is a test comment",
                "reactions": []
            }
        ],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the comment from the post
    response = client.delete('/posts/1/comments/1', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Comment deleted successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 53- Test comment deletion from a non-existent post
def test_delete_comment_from_non_existent_post(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the comment from a non-existent post
    response = client.delete('/posts/999/comments/1', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Post not found" }

# 54- Test comment deletion from a non-existent comment on a post
def test_delete_comment_from_non_existent_comment_on_post(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a post into the database
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "reactions": [],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the comment from a non-existent comment on the post
    response = client.delete('/posts/1/comments/999', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Comment not found" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 55- Test successful comment deletion from a destination
def test_delete_comment_from_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination with a comment into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [
            {
                "comment_id": 1,
                "user_id": 1,
                "userName": "test",
                "comment": "This is a test comment",
                "reactions": []
            }
        ],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the comment from the destination
    response = client.delete('/destinations/1/comments/1', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Comment deleted successfully" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 56- Test comment deletion from a non-existent destination
def test_delete_comment_from_non_existent_destination(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the comment from a non-existent destination
    response = client.delete('/destinations/999/comments/1', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Destination not found" }

# 57- Test comment deletion from a non-existent comment on a destination
def test_delete_comment_from_non_existent_comment_on_destination(client):
    # Clean up the database before starting the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the comment from a non-existent comment on the destination
    response = client.delete('/destinations/1/comments/999', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Comment not found" }

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})
    mongo_db["destinations"].delete_many({})
# 58- Test get all destinations
def test_get_destinations(client):
    # Clean up the database before starting the test
    mongo_db["destinations"].delete_many({})

    # Insert some destinations into the database
    mongo_db["destinations"].insert_many([
        {"id": 1, "name": "Destination 1", "description": "Description 1", "city": "City 1", "country": "Country 1", "media": ["image1.jpg"]},
        {"id": 2, "name": "Destination 2", "description": "Description 2", "city": "City 2", "country": "Country 2", "media": ["image2.jpg"]}
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Get all destinations
    response = client.get('/destinations', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert len(response.json) == 2
    assert response.json[0]["name"] == "Destination 1"
    assert response.json[1]["name"] == "Destination 2"

    # Clean up the database after the test
    mongo_db["destinations"].delete_many({})
# 59- Test successful destination creation
def test_add_destination(client):
    # Clean up the database before starting the test
    mongo_db["destinations"].delete_many({})

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Add a new destination
    response = client.post('/destinations', data={
        "name": "New Destination",
        "description": "A beautiful place",
        "city": "Test City",
        "country": "Test Country",
        "media": "image1.jpg,image2.jpg"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Destination added successfully" }

    # Clean up the database after the test
    mongo_db["destinations"].delete_many({})

# 60- Test destination creation with missing fields
def test_add_destination_missing_fields(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Add a new destination with missing fields
    response = client.post('/destinations', data={
        "name": "New Destination",
        "description": "A beautiful place",
        "city": "Test City"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "All fields are required" }

# 61- Test destination creation with duplicate name
def test_add_destination_duplicate_name(client):
    # Clean up the database before starting the test
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Duplicate Destination",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Add a new destination with a duplicate name
    response = client.post('/destinations', data={
        "name": "Duplicate Destination",
        "description": "A beautiful place",
        "city": "Test City",
        "country": "Test Country",
        "media": "image1.jpg,image2.jpg"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Destination name must be unique" }

    # Clean up the database after the test
    mongo_db["destinations"].delete_many({})
# 62- Test successful destination edit
def test_edit_destination(client):
    # Clean up the database before starting the test
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the destination
    response = client.put('/destinations/1', data={
        "name": "Edited Destination",
        "description": "An edited description",
        "city": "Edited City",
        "country": "Edited Country",
        "media": "image3.jpg,image4.jpg"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Destination edited successfully" }

    # Clean up the database after the test
    mongo_db["destinations"].delete_many({})

# 63- Test destination edit with non-existent destination
def test_edit_non_existent_destination(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit a non-existent destination
    response = client.put('/destinations/999', data={
        "name": "Edited Destination",
        "description": "An edited description",
        "city": "Edited City",
        "country": "Edited Country",
        "media": "image3.jpg,image4.jpg"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Destination not found" }

# 64- Test destination edit by unauthorized user
def test_edit_unauthorized_destination(client):
    # Clean up the database before starting the test
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 2,
        "userName": "User2",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the destination
    response = client.put('/destinations/1', data={
        "name": "Edited Destination",
        "description": "An edited description",
        "city": "Edited City",
        "country": "Edited Country",
        "media": "image3.jpg,image4.jpg"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 401
    assert response.json == { "error": "Unauthorized" }

    # Clean up the database after the test
    mongo_db["destinations"].delete_many({})
# 65- Test successful destination deletion
def test_delete_destination(client):
    # Clean up the database before starting the test
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the destination
    response = client.delete('/destinations/1', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Destination deleted successfully" }

    # Clean up the database after the test
    mongo_db["destinations"].delete_many({})

# 66- Test destination deletion with non-existent destination
def test_delete_non_existent_destination(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete a non-existent destination
    response = client.delete('/destinations/999', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Destination not found" }

# 67- Test destination deletion by unauthorized user
def test_delete_unauthorized_destination(client):
    # Clean up the database before starting the test
    mongo_db["destinations"].delete_many({})

    # Insert a destination into the database
    mongo_db["destinations"].insert_one({
        "id": 1,
        "user_id": 2,
        "userName": "User2",
        "name": "Destination 1",
        "description": "This is a test destination",
        "city": "Test City",
        "country": "Test Country",
        "media": ["image1.jpg", "image2.jpg"],
        "comments": [],
        "reactions": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the destination
    response = client.delete('/destinations/1', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 401
    assert response.json == { "error": "Unauthorized" }

    # Clean up the database after the test
    mongo_db["destinations"].delete_many({})

# 68- Test get trip goals of a user
def test_get_trip_goals(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "followers": []
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Get trip goals of the user
    response = client.get('/trip-goals/1', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json["user_id"] == 1
    assert len(response.json["destinations"]) == 2

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})

# 69- Test get trip goals of a non-existent user
def test_get_trip_goals_non_existent_user(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Get trip goals of a non-existent user
    response = client.get('/trip-goals/999', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "User not found" }
# 70- Test successful trip goal creation
def test_add_trip_goal(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert some destinations into the database
    mongo_db["destinations"].insert_many([
        {"id": 1, "name": "Destination 1"},
        {"id": 2, "name": "Destination 2"}
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Add a new trip goal
    response = client.post('/trip-goals', data={
        "destination_ids": "1,2"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Trip goal added successfully" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 71- Test trip goal creation with missing destination IDs
def test_add_trip_goal_missing_destination_ids(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Add a new trip goal with missing destination IDs
    response = client.post('/trip-goals', data={}, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Destination IDs are required" }

# 72- Test trip goal creation with invalid destination ID format
def test_add_trip_goal_invalid_destination_format(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Add a new trip goal with invalid destination ID format
    response = client.post('/trip-goals', data={
        "destination_ids": "invalid_format"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Invalid format for destination IDs" }

# 73- Test trip goal creation with non-existent destination
def test_add_trip_goal_non_existent_destination(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Add a new trip goal with non-existent destination
    response = client.post('/trip-goals', data={
        "destination_ids": "999"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Destination with id 999 not found" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})
# 74- Test successful trip goal edit
def test_edit_trip_goal(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert some destinations into the database
    mongo_db["destinations"].insert_many([
        {"id": 1, "name": "Destination 1"},
        {"id": 2, "name": "Destination 2"}
    ])

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "destinations": [
            {"id": 1, "name": "Destination 1"}
        ],
        "followers": []
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the trip goal
    response = client.put('/trip-goals/1', data={
        "destination_ids": "1,2"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Trip goal edited successfully" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 75- Test trip goal edit with non-existent trip goal
def test_edit_non_existent_trip_goal(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit a non-existent trip goal
    response = client.put('/trip-goals/999', data={
        "destination_ids": "1,2"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Trip goal not found" }

# 76- Test trip goal edit by unauthorized user
def test_edit_unauthorized_trip_goal(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 2,
        "userName": "User2",
        "destinations": [
            {"id": 1, "name": "Destination 1"}
        ],
        "followers": []
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the trip goal
    response = client.put('/trip-goals/1', data={
        "destination_ids": "1,2"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 401
    assert response.json == { "error": "Unauthorized" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 77- Test trip goal edit with missing destination IDs
def test_edit_trip_goal_missing_destination_ids(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "destinations": [
            {"id": 1, "name": "Destination 1"}
        ],
        "followers": []
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the trip goal with missing destination IDs
    response = client.put('/trip-goals/1', data={}, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Destination IDs are required" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 78- Test trip goal edit with invalid destination ID format
def test_edit_trip_goal_invalid_destination_format(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "destinations": [
            {"id": 1, "name": "Destination 1"}
        ],
        "followers": []
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the trip goal with invalid destination ID format
    response = client.put('/trip-goals/1', data={
        "destination_ids": "invalid_format"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "Invalid format for destination IDs" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 79- Test trip goal edit with non-existent destination
def test_edit_trip_goal_non_existent_destination(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "destinations": [
            {"id": 1, "name": "Destination 1"}
        ],
        "followers": []
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Edit the trip goal with non-existent destination
    response = client.put('/trip-goals/1', data={
        "destination_ids": "999"
    }, headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Destination with id 999 not found" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 80- Test successful trip goal deletion
def test_delete_trip_goal(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "followers": []
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the trip goal
    response = client.delete('/trip-goals/1', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Trip goal deleted successfully" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 81- Test trip goal deletion with non-existent trip goal
def test_delete_non_existent_trip_goal(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete a non-existent trip goal
    response = client.delete('/trip-goals/999', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Trip goal not found" }

# 82- Test trip goal deletion by unauthorized user
def test_delete_unauthorized_trip_goal(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 2,
        "userName": "User2",
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "followers": []
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Delete the trip goal
    response = client.delete('/trip-goals/1', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 401
    assert response.json == { "error": "Unauthorized" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})
    
# 83- Test successful trip goal follow
def test_follow_trip_goal(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "followers": []
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Follow the trip goal
    response = client.post('/trip-goals/1/follow', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Trip goal followed successfully" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 84- Test follow non-existent trip goal
def test_follow_non_existent_trip_goal(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Follow a non-existent trip goal
    response = client.post('/trip-goals/999/follow', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Trip goal not found" }

# 85- Test follow trip goal already followed
def test_follow_already_followed_trip_goal(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "followers": [
            {
                "user_id": 1,
                "userName": "test"
            }
        ]
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Follow the trip goal again
    response = client.post('/trip-goals/1/follow', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "User already follows this trip goal" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})
    
# 86- Test successful trip goal unfollow
def test_unfollow_trip_goal(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "followers": [
            {
                "user_id": 1,
                "userName": "test"
            }
        ]
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Unfollow the trip goal
    response = client.post('/trip-goals/1/unfollow', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert response.json == { "message": "Trip goal unfollowed successfully" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 87- Test unfollow non-existent trip goal
def test_unfollow_non_existent_trip_goal(client):
    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Unfollow a non-existent trip goal
    response = client.post('/trip-goals/999/unfollow', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 404
    assert response.json == { "error": "Trip goal not found" }

# 88- Test unfollow trip goal not followed
def test_unfollow_not_followed_trip_goal(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

    # Insert a trip goal into the database
    mongo_db["tripGoals"].insert_one({
        "id": 1,
        "user_id": 1,
        "userName": "test",
        "destinations": [
            {"id": 1, "name": "Destination 1"},
            {"id": 2, "name": "Destination 2"}
        ],
        "followers": []
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Unfollow the trip goal not followed
    response = client.post('/trip-goals/1/unfollow', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 400
    assert response.json == { "error": "User does not follow this trip goal" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    mongo_db["destinations"].delete_many({})

# 89- Test get followed trip goals
def test_get_followed_trip_goals(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    pg_conn.cursor().execute("DELETE FROM trip_goals")

    # Insert some trip goals into the database
    mongo_db["tripGoals"].insert_many([
        {"id": 1, "user_id": 1, "userName": "test", "destinations": [{"id": 1, "name": "Destination 1"}], "followers": []},
        {"id": 2, "user_id": 2, "userName": "User2", "destinations": [{"id": 2, "name": "Destination 2"}], "followers": []}
    ])

    # Insert followed trip goals into PostgreSQL
    cursor = pg_conn.cursor()
    cursor.execute("INSERT INTO trip_goals (trip_goal_id, sub) VALUES (1, 1), (2, 1)")
    pg_conn.commit()

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Get followed trip goals
    response = client.get('/trip-goals/followed', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert len(response.json) == 2
    assert response.json[0]["id"] == 1
    assert response.json[1]["id"] == 2

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    cursor.execute("DELETE FROM trip_goals")
    pg_conn.commit()

# 90- Test get followed trip goals with no followed goals
def test_get_followed_trip_goals_no_followed(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    pg_conn.cursor().execute("DELETE FROM trip_goals")

    # Insert some trip goals into the database
    mongo_db["tripGoals"].insert_many([
        {"id": 1, "user_id": 1, "userName": "test", "destinations": [{"id": 1, "name": "Destination 1"}], "followers": []},
        {"id": 2, "user_id": 2, "userName": "User2", "destinations": [{"id": 2, "name": "Destination 2"}], "followers": []}
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Get followed trip goals
    response = client.get('/trip-goals/followed', headers={ "Authorization": token, "Session-ID": session_id })
    assert response.status_code == 200
    assert len(response.json) == 0

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    pg_conn.cursor().execute("DELETE FROM trip_goals")
    pg_conn.commit()

# 91- Test get followed trip goals with invalid session
def test_get_followed_trip_goals_invalid_session(client):
    # Clean up the database before starting the test
    mongo_db["tripGoals"].delete_many({})
    pg_conn.cursor().execute("DELETE FROM trip_goals")

    # Insert some trip goals into the database
    mongo_db["tripGoals"].insert_many([
        {"id": 1, "user_id": 1, "userName": "test", "destinations": [{"id": 1, "name": "Destination 1"}], "followers": []},
        {"id": 2, "user_id": 2, "userName": "User2", "destinations": [{"id": 2, "name": "Destination 2"}], "followers": []}
    ])

    # Insert followed trip goals into PostgreSQL
    cursor = pg_conn.cursor()
    cursor.execute("INSERT INTO trip_goals (trip_goal_id, sub) VALUES (1, 1), (2, 1)")
    pg_conn.commit()

    # Login to get the authorization token
    login_response = client.post('/login', data={ "username": "test", "password": "test" })
    token = login_response.json["token"]

    # Get followed trip goals with invalid session
    response = client.get('/trip-goals/followed', headers={ "Authorization": token, "Session-ID": "" })
    assert response.status_code == 401
    assert response.json == { "error": "Session-ID is required" }

    # Clean up the database after the test
    mongo_db["tripGoals"].delete_many({})
    cursor.execute("DELETE FROM trip_goals")
    pg_conn.commit()

# 92- Test successful caching of popular posts

# 92- Test successful caching of popular posts
def test_cache_popular_posts(client):
    # Clean up the database and Redis before starting the test
    mongo_db["posts"].delete_many({})
    redis_client.flushall()

    # Insert posts into MongoDB
    mongo_db["posts"].insert_many([
        {
            "user_id": 1,
            "id": 1,
            "userName": "test",
            "content": "This is a test post with 2 reactions",
            "media": ["image1.jpg", "image2.jpg"],
            "destinations": [{"id": 1, "name": "Destination 1"}],
            "reactions": [
                {"user_id": 1, "userName": "test", "reaction": "like"},
                {"user_id": 2, "userName": "test2", "reaction": "love"}
            ],
            "comments": [],
            "created_at": "2024-10-12T09:00:00Z"
        },
        {
            "user_id": 2,
            "id": 2,
            "userName": "test2",
            "content": "This is a test post with 1 reaction",
            "media": ["image3.jpg", "image4.jpg"],
            "destinations": [{"id": 2, "name": "Destination 2"}],
            "reactions": [
                {"user_id": 1, "userName": "test", "reaction": "like"}
            ],
            "comments": [],
            "created_at": "2024-10-12T10:00:00Z"
        }
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={"username": "test", "password": "test"})
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Cache popular posts
    response = client.post('/cache-posts', headers={"Authorization": token, "Session-ID": session_id})
    assert response.status_code == 200
    assert response.json == {"message": "Posts cached successfully"}

    # Verify that the popular post is cached in Redis
    cached_post = redis_client.get("post:1")
    assert cached_post is not None
    assert "This is a test post with 2 reactions" in cached_post.decode('utf-8')

    # Verify that the non-popular post is not cached in Redis
    non_cached_post = redis_client.get("post:2")
    assert non_cached_post is None

    # Clean up the database and Redis after the test
    mongo_db["posts"].delete_many({})
    redis_client.flushall()

# 93- Test caching posts with no popular posts
def test_cache_no_popular_posts(client):
    # Clean up the database and Redis before starting the test
    mongo_db["posts"].delete_many({})
    redis_client.flushall()

    # Insert posts into MongoDB
    mongo_db["posts"].insert_many([
        {
            "user_id": 1,
            "id": 1,
            "userName": "test",
            "content": "This is a test post with 1 reaction",
            "media": ["image1.jpg", "image2.jpg"],
            "destinations": [{"id": 1, "name": "Destination 1"}],
            "reactions": [
                {"user_id": 1, "userName": "test", "reaction": "like"}
            ],
            "comments": [],
            "created_at": "2024-10-12T09:00:00Z"
        },
        {
            "user_id": 2,
            "id": 2,
            "userName": "test2",
            "content": "This is another test post with 1 reaction",
            "media": ["image3.jpg", "image4.jpg"],
            "destinations": [{"id": 2, "name": "Destination 2"}],
            "reactions": [
                {"user_id": 1, "userName": "test", "reaction": "like"}
            ],
            "comments": [],
            "created_at": "2024-10-12T10:00:00Z"
        }
    ])

    # Login to get the authorization token
    login_response = client.post('/login', data={"username": "test", "password": "test"})
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Cache popular posts
    response = client.post('/cache-posts', headers={"Authorization": token, "Session-ID": session_id})
    assert response.status_code == 200
    assert response.json == {"message": "Posts cached successfully"}

    # Verify that no posts are cached in Redis
    cached_post_1 = redis_client.get("post:1")
    cached_post_2 = redis_client.get("post:2")
    assert cached_post_1 is None
    assert cached_post_2 is None

    # Clean up the database and Redis after the test
    mongo_db["posts"].delete_many({})
    redis_client.flushall()

# 94- Test get post from Redis
def test_get_post_from_redis(client):
    # Clean up the database and Redis before starting the test
    mongo_db["posts"].delete_many({})
    redis_client.flushall()

    # Insert a post into Redis
    post_data = {
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [{"id": 1, "name": "Destination 1"}],
        "reactions": [],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    }
    with app.app_context():
        redis_client.set(f"post:1", jsonify(post_data).get_data(as_text=True))

    # Login to get the authorization token
    login_response = client.post('/login', data={"username": "test", "password": "test"})
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Get the post from Redis
    response = client.get('/posts/1', headers={"Authorization": token, "Session-ID": session_id})
    assert response.status_code == 200
    assert response.json["content"] == "This is a test post"

    # Clean up the database and Redis after the test
    redis_client.flushall()

# 95- Test get post from MongoDB
def test_get_post_from_mongodb(client):
    # Clean up the database and Redis before starting the test
    mongo_db["posts"].delete_many({})
    redis_client.flushall()

    # Insert a post into MongoDB
    mongo_db["posts"].insert_one({
        "user_id": 1,
        "id": 1,
        "userName": "test",
        "content": "This is a test post",
        "media": ["image1.jpg", "image2.jpg"],
        "destinations": [{"id": 1, "name": "Destination 1"}],
        "reactions": [],
        "comments": [],
        "created_at": "2024-10-12T09:00:00Z"
    })

    # Login to get the authorization token
    login_response = client.post('/login', data={"username": "test", "password": "test"})
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Get the post from MongoDB
    response = client.get('/posts/1', headers={"Authorization": token, "Session-ID": session_id})
    assert response.status_code == 200
    assert response.json["content"] == "This is a test post"

    # Clean up the database after the test
    mongo_db["posts"].delete_many({})

# 96- Test get non-existent post
def test_get_non_existent_post(client):
    # Clean up the database and Redis before starting the test
    mongo_db["posts"].delete_many({})
    redis_client.flushall()

    # Login to get the authorization token
    login_response = client.post('/login', data={"username": "test", "password": "test"})
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Try to get a non-existent post
    response = client.get('/posts/999', headers={"Authorization": token, "Session-ID": session_id})
    assert response.status_code == 404
    assert response.json == {"error": "Post not found"}

    # Clean up the database and Redis after the test
    redis_client.flushall()

# 97- Test get active sessions
def test_get_active_sessions(client):
    # Clean up Redis before starting the test
    redis_client.flushall()

    # Insert some sessions into Redis
    redis_client.setex("session:1", 36000, "token1")
    redis_client.setex("session:2", 36000, "token2")

    # Login to get the authorization token
    login_response = client.post('/login', data={"username": "user1", "password": "password1"})
    token = login_response.json["token"]
    session_id = login_response.json["session_id"]

    # Get active sessions
    response = client.get('/sessions', headers={"Authorization": token, "Session-ID": session_id})
    assert response.status_code == 200
    assert "session:1" in response.json
    assert "session:2" in response.json

    # Clean up Redis after the test
    redis_client.flushall()

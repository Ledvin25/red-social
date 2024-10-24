-- Este archivo se encarga de crear la base de datos y las tablas necesarias para el proyecto

-- Tabla de usuarios, contiene el id del usuario, el nombre de usuario y la fecha de creación.
CREATE TABLE users (
    sub SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    password VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de posts, contiene el id del post, el id del usuario que lo creó y la fecha de creación.
CREATE TABLE posts (
    post_id SERIAL PRIMARY KEY,
    sub INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sub) REFERENCES users(sub)
);

-- Tabla para los trip goals que estoy siguiendo en mi cuenta
CREATE TABLE trip_goals (
    trip_goal_id INT NULL,
    sub INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sub) REFERENCES users(sub)
);


-- Inserts de prueba para la tabla de usuarios
INSERT INTO users (username, password) VALUES ('user1', 'password1');
INSERT INTO users (username, password) VALUES ('user2', 'password2');
INSERT INTO users (username, password) VALUES ('user3', 'password3');
INSERT INTO users (username, password) VALUES ('user4', 'password4');

-- Inserts de prueba para la tabla de posts
INSERT INTO posts (sub) VALUES (1);

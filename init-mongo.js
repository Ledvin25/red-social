// Definir la base de datos
db = db.getSiblingDB('mydatabase'); // Nombre de la base de datos (hay que cambiarlo)

// Crear la colección para posts
db.createCollection('posts');

// Crear la colección para destinos
db.createCollection('destinations');

// Crear la colección para Objetivos de Viajes
db.createCollection('tripGoals');

// Insertar datos de ejemplo

// post
db.posts.insertOne({
    user_id: 2,
    id: 1,
    userName: "User2",
    content: "Texto de la publicación...",
    media: ["image_link_1", "image_link_2"],
    destinations: [
        {
            id: 1,
            name: "París",
        }
    ],
    reactions: [
      {
        user_id: 2,
        userName: "User2",
        reaction: "like",
      }
    ],
    comments: [
      {
        comment_id: 1,
        user_id: 2,
        userName: "User2",
        comment: "Gran publicación!",
        reactions: [
          {
            user_id: 3,
            userName: "User3",
            reaction: "like",
          }
        ],
        created_at: "2024-10-12T10:00:00Z"
      }
    ],
    created_at: "2024-10-12T09:00:00Z"
  });  

// destinos
db.destinations.insertOne({
    user_id: 2,
    userName: "User1",
    id: 1,
    name: "París",
    description: "Ciudad del amor",
    city: "París",
    country: "Francia",
    media: ["image_link_1", "image_link_2"],
    comments: [
        {
        comment_id: 1,
        user_id: 2,
        userName: "User1",
        comment: "Gran destino!",
        reactions: [
            {
              user_id: 3,
              userName: "User3",
              reaction: "like",
            }
        ],
        created_at: "2024-10-12T10:00:00Z"
        }
    ],
    reactions: [
        {
        user_id: 2,
        userName: "User2",
        reaction: "love",
        }
    ]
});

// Objetivos de Viajes
db.tripGoals.insertOne({
    id: 1,
    userName: "User1",
    user_id: 2,
    destinations: [
        {
            id: 1,
            name: "París"
        },
        {
            id: 2,
            name: "Tokio"
        }
    ],
    followers: [
        {
            user_id: 2,
            userName: "User2"
        },
        {
            user_id: 3,
            userName: "User3"
        },
        {
            user_id: 4,
            userName: "User4"
        }
    ]
});
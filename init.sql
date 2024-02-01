CREATE TABLE category (
    id serial PRIMARY KEY,
    name VARCHAR(51) NOT NULL,
    parent_id INT DEFAULT NULL,
    FOREIGN KEY (parent_id) REFERENCES category(id) ON DELETE CASCADE
);

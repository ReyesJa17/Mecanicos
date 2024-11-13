CREATE DATABASE IF NOT EXISTS mecanicos;
USE mecanicos;

-- Table: Productos
CREATE TABLE IF NOT EXISTS Productos (
    ID INT PRIMARY KEY NOT NULL AUTO_INCREMENT,
    Nombre VARCHAR(255) NOT NULL,
    Categoria VARCHAR(255) NOT NULL
);

-- Set the starting value of AUTO_INCREMENT to 1 every time the table is recreated or modified
ALTER TABLE Productos AUTO_INCREMENT = 1;

-- Table: Orden_Entrada
CREATE TABLE IF NOT EXISTS Orden_Entrada (
    ID_Entrada INT PRIMARY KEY AUTO_INCREMENT,
    Fecha_Entrada DATE NOT NULL,
    Status ENUM('liberada', 'proceso', 'inactiva') NOT NULL,
    Fecha_Salida DATE,
    ID_Camion VARCHAR(255),
    Motivo_Entrada TEXT,
    Motivo_Salida TEXT,
    Tipo ENUM('CONSUMIBLE', 'PREVENTIVO', 'CORRECTIVO'),
    Kilometraje INT,
    Lugar ENUM('PUEBLA', 'VILLA HERMOSA', 'GUADALAJARA'),
    hora_registro TIME,
    hora_salida TIME
);

-- Table: Camion
CREATE TABLE IF NOT EXISTS Camion (
    VIN VARCHAR(255) PRIMARY KEY,
    NumeroUnidad INT NOT NULL,
    Kilometraje INT NOT NULL,
    Marca VARCHAR(255) NOT NULL,
    Modelo VARCHAR(255) NOT NULL
);

-- Table: Productos_Servicio
CREATE TABLE IF NOT EXISTS Productos_Servicio (
    ID_Orden INT NOT NULL,
    ID_Producto INT NOT NULL,
    Cantidad INT NOT NULL,
    PRIMARY KEY (ID_Orden, ID_Producto),
    FOREIGN KEY (ID_Orden) REFERENCES Orden_Entrada(ID_Entrada),
    FOREIGN KEY (ID_Producto) REFERENCES Productos(ID)
);

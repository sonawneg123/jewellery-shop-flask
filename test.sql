-- ============================================================
-- JEWELLERY SHOP - MySQL Schema
-- Compatible with AWS RDS MySQL 8.0+
-- ============================================================

CREATE DATABASE IF NOT EXISTS jewellery_shop CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE jewellery_shop;

-- ============================================================
-- TABLE: clients
-- ============================================================
CREATE TABLE IF NOT EXISTS clients (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(120)        NOT NULL,
    email         VARCHAR(255)        NOT NULL UNIQUE,
    mobile        VARCHAR(15)         NOT NULL,
    password_hash VARCHAR(255)        NOT NULL,
    budget        DECIMAL(12,2)       NOT NULL DEFAULT 0.00,
    created_at    TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP           NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_mobile (mobile)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLE: categories
-- ============================================================
CREATE TABLE IF NOT EXISTS categories (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    icon        VARCHAR(50),
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLE: jewellery_items
-- ============================================================
CREATE TABLE IF NOT EXISTS jewellery_items (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    category_id     INT UNSIGNED NOT NULL,
    name            VARCHAR(200)    NOT NULL,
    description     TEXT,
    metal_type      ENUM('gold','silver','platinum','rose_gold','white_gold') NOT NULL DEFAULT 'gold',
    metal_purity    VARCHAR(10)     COMMENT '18K, 22K, 925, etc.',
    weight_grams    DECIMAL(8,3)    NOT NULL DEFAULT 0.000,
    making_charges  DECIMAL(10,2)   NOT NULL DEFAULT 0.00   COMMENT 'Fixed making charges in INR',
    stone_charges   DECIMAL(10,2)   NOT NULL DEFAULT 0.00   COMMENT 'Stone/diamond charges in INR',
    image_url       VARCHAR(500),
    stock           INT UNSIGNED    NOT NULL DEFAULT 1,
    is_active       TINYINT(1)      NOT NULL DEFAULT 1,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
    INDEX idx_category (category_id),
    INDEX idx_metal (metal_type),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLE: metal_prices  (real-time price feed)
-- ============================================================
CREATE TABLE IF NOT EXISTS metal_prices (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    metal_type  ENUM('gold','silver','platinum','rose_gold','white_gold') NOT NULL,
    price_per_gram DECIMAL(12,4)  NOT NULL COMMENT 'Price in INR per gram',
    source      VARCHAR(100)      DEFAULT 'manual',
    fetched_at  TIMESTAMP         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_metal_time (metal_type, fetched_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLE: carts
-- ============================================================
CREATE TABLE IF NOT EXISTS carts (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    client_id   INT UNSIGNED NOT NULL,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_client_cart (client_id),
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLE: cart_items
-- ============================================================
CREATE TABLE IF NOT EXISTS cart_items (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cart_id         INT UNSIGNED  NOT NULL,
    item_id         INT UNSIGNED  NOT NULL,
    quantity        INT UNSIGNED  NOT NULL DEFAULT 1,
    price_snapshot  DECIMAL(12,2) NOT NULL COMMENT 'Price at time of adding to cart',
    added_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cart_id)  REFERENCES carts(id)           ON DELETE CASCADE,
    FOREIGN KEY (item_id)  REFERENCES jewellery_items(id) ON DELETE CASCADE,
    UNIQUE KEY uq_cart_item (cart_id, item_id),
    INDEX idx_cart (cart_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLE: orders
-- ============================================================
CREATE TABLE IF NOT EXISTS orders (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    client_id       INT UNSIGNED    NOT NULL,
    total_amount    DECIMAL(12,2)   NOT NULL,
    status          ENUM('pending','confirmed','processing','shipped','delivered','cancelled') NOT NULL DEFAULT 'pending',
    notes           TEXT,
    created_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE RESTRICT,
    INDEX idx_client (client_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- TABLE: order_items
-- ============================================================
CREATE TABLE IF NOT EXISTS order_items (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id        INT UNSIGNED  NOT NULL,
    item_id         INT UNSIGNED  NOT NULL,
    quantity        INT UNSIGNED  NOT NULL DEFAULT 1,
    unit_price      DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id)           ON DELETE CASCADE,
    FOREIGN KEY (item_id)  REFERENCES jewellery_items(id)  ON DELETE RESTRICT,
    INDEX idx_order (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- SEED: categories
-- ============================================================
INSERT INTO categories (name, description, icon) VALUES
('Rings',     'Engagement, wedding & fashion rings',    'ring'),
('Necklaces', 'Chains, pendants & chokers',             'necklace'),
('Bangles',   'Traditional & modern bangles',           'bangle'),
('Earrings',  'Studs, drops, hoops & chandeliers',      'earring'),
('Bracelets', 'Gold & diamond bracelets',               'bracelet'),
('Mangalsutra','Traditional mangalsutra designs',       'mangalsutra');

-- ============================================================
-- SEED: initial metal prices (INR per gram)
-- ============================================================
INSERT INTO metal_prices (metal_type, price_per_gram, source) VALUES
('gold',       6050.00, 'seed'),
('silver',       75.50, 'seed'),
('platinum',   3200.00, 'seed'),
('rose_gold',  5850.00, 'seed'),
('white_gold', 5900.00, 'seed');

-- ============================================================
-- SEED: jewellery items
-- ============================================================
INSERT INTO jewellery_items (category_id, name, description, metal_type, metal_purity, weight_grams, making_charges, stone_charges, image_url, stock) VALUES
-- Rings
(1, 'Solitaire Diamond Ring',     'Classic 6-prong solitaire with brilliant-cut diamond',        'gold',       '18K', 4.200, 2500.00, 35000.00, 'https://images.unsplash.com/photo-1605100804763-247f67b3557e?w=400', 5),
(1, 'Floral Kundan Ring',         'Hand-crafted kundan ring with emerald centre stone',           'gold',       '22K', 6.800, 3200.00, 8000.00,  'https://images.unsplash.com/photo-1589128777073-263566ae5e4d?w=400', 8),
(1, 'Rose Gold Band',             'Minimalist rose gold band with diamond pavé',                  'rose_gold',  '18K', 3.500, 1800.00, 12000.00, 'https://images.unsplash.com/photo-1543294001-f7cd5d7fb516?w=400', 10),
(1, 'Platinum Eternity Ring',     'Full eternity platinum band set with VVS diamonds',            'platinum',   '950', 5.000, 4500.00, 55000.00, 'https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=400', 3),
-- Necklaces
(2, 'Polki Diamond Necklace',     'Bridal polki set with uncut diamonds & emeralds',              'gold',       '22K',28.500,12000.00,180000.00,'https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=400', 2),
(2, 'Diamond Riviera Necklace',   'Tennis-style riviera with 1ct total diamond weight',           'white_gold', '18K', 8.200, 6000.00, 95000.00, 'https://images.unsplash.com/photo-1611085583191-a3b181a88401?w=400', 4),
(2, 'Temple Lakshmi Necklace',    'Traditional temple jewellery with antique finish',             'gold',       '22K',22.000, 9500.00, 5000.00,  'https://images.unsplash.com/photo-1602751584552-8ba73aad10e1?w=400', 6),
(2, 'Layered Delicate Chain',     'Three-layer 18K gold chain with pearl drops',                  'gold',       '18K', 5.500, 2200.00, 3500.00,  'https://images.unsplash.com/photo-1573408301185-9519f94bf2f4?w=400', 12),
-- Bangles
(3, 'Nakshi Kadaa Set of 2',      'Handcrafted nakshi-work heavy gold bangles',                   'gold',       '22K',38.000,15000.00,    0.00,  'https://images.unsplash.com/photo-1611591437281-460bfbe1220a?w=400', 5),
(3, 'Diamond Bangle',             'Channel-set diamond bangle in white gold',                     'white_gold', '18K',12.000, 8000.00, 65000.00, 'https://images.unsplash.com/photo-1602173574767-37ac01994b2a?w=400', 3),
(3, 'Silver Oxidised Kada',       'Boho-style oxidised silver bangle with tribal motifs',         'silver',     '925',45.000, 800.00,     0.00,  'https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=400', 20),
-- Earrings
(4, 'Jhumka Chandelier Earrings', 'Classic gold jhumka with pearl & enamel work',                 'gold',       '22K',10.500, 4500.00, 2500.00,  'https://images.unsplash.com/photo-1506630448388-4e683c67ddb0?w=400', 10),
(4, 'Diamond Stud Earrings',      'GIA-certified 0.5ct each round brilliants in 18K',             'gold',       '18K', 2.200, 1500.00, 42000.00, 'https://images.unsplash.com/photo-1635797255620-fa1ca37f7ba8?w=400', 8),
(4, 'Emerald Drop Earrings',      'Colombian emerald drops set in 22K gold',                      'gold',       '22K', 7.800, 3800.00, 28000.00, 'https://images.unsplash.com/photo-1598560917505-59a3ad559071?w=400', 6),
-- Bracelets
(5, 'Tennis Diamond Bracelet',    '4ct diamond tennis bracelet in 18K white gold',                'white_gold', '18K',12.500,10000.00,185000.00,'https://images.unsplash.com/photo-1624913503273-5f9c4e980dba?w=400', 2),
(5, 'Gold Charm Bracelet',        'Customisable 22K charm bracelet with 5 charms',                'gold',       '22K', 9.500, 3500.00, 1500.00,  'https://images.unsplash.com/photo-1573241337978-b6b3cf483c4d?w=400', 7),
-- Mangalsutra
(6, 'Black Bead Mangalsutra',     'Traditional 22K gold mangalsutra with black beads, 18 inch',  'gold',       '22K',11.000, 4000.00,    0.00,  'https://images.unsplash.com/photo-1601821765780-754fa98637c1?w=400', 15),
(6, 'Diamond Mangalsutra',        'Contemporary diamond mangalsutra pendant on black chain',      'gold',       '18K', 5.500, 3500.00, 22000.00, 'https://images.unsplash.com/photo-1612118887835-20a7f00ef001?w=400', 8);

-- ============================================================
-- USEFUL VIEWS
-- ============================================================

-- View: current item prices with live metal rates
CREATE OR REPLACE VIEW vw_item_prices AS
SELECT
    ji.id,
    ji.name,
    ji.description,
    ji.metal_type,
    ji.metal_purity,
    ji.weight_grams,
    ji.making_charges,
    ji.stone_charges,
    ji.image_url,
    ji.stock,
    c.name AS category_name,
    mp.price_per_gram,
    mp.fetched_at  AS price_updated_at,
    ROUND(
        (ji.weight_grams * mp.price_per_gram) + ji.making_charges + ji.stone_charges,
        2
    ) AS total_price
FROM jewellery_items ji
JOIN categories c ON c.id = ji.category_id
JOIN (
    SELECT metal_type, price_per_gram, fetched_at
    FROM metal_prices mp1
    WHERE fetched_at = (
        SELECT MAX(mp2.fetched_at) FROM metal_prices mp2
        WHERE mp2.metal_type = mp1.metal_type
    )
) mp ON mp.metal_type = ji.metal_type
WHERE ji.is_active = 1;

-- View: cart summary per client
CREATE OR REPLACE VIEW vw_cart_summary AS
SELECT
    cl.id   AS client_id,
    cl.name AS client_name,
    cl.email,
    cl.budget,
    COUNT(ci.id)    AS item_count,
    SUM(ci.quantity) AS total_qty,
    SUM(ci.price_snapshot * ci.quantity) AS cart_total
FROM clients cl
LEFT JOIN carts ca  ON ca.client_id = cl.id
LEFT JOIN cart_items ci ON ci.cart_id = ca.id
GROUP BY cl.id, cl.name, cl.email, cl.budget;

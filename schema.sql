-- Reference DDL for MySQL 8.
--
-- The application creates these tables itself on startup from the SQLAlchemy
-- models in `app/models/`. This file is the human-readable copy: use it to
-- review the shape of the database, or to provision it ahead of time.

CREATE TABLE products (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL UNIQUE,
  category VARCHAR(100),
  price DECIMAL(10, 2) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  INDEX ix_products_category (category)
);

-- One row per product: the unique index is what makes "current stock" a
-- single number rather than a sum over rows.
CREATE TABLE inventory (
  id INT PRIMARY KEY AUTO_INCREMENT,
  product_id INT NOT NULL,
  quantity INT NOT NULL DEFAULT 0,
  CONSTRAINT ck_inventory_nonnegative CHECK (quantity >= 0),
  UNIQUE INDEX ix_inventory_product_id (product_id),
  INDEX ix_inventory_quantity (quantity),
  FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Every analytics query filters or groups on sale_date, and the per-product
-- history reads (product_id, sale_date) together.
CREATE TABLE sales (
  id INT PRIMARY KEY AUTO_INCREMENT,
  product_id INT NOT NULL,
  quantity_sold INT NOT NULL,
  sale_date DATE NOT NULL,
  total_amount DECIMAL(10, 2) NOT NULL,
  INDEX ix_sales_sale_date (sale_date),
  INDEX ix_sales_product_date (product_id, sale_date),
  FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Append-only audit trail. Written in the same transaction as the stock
-- level it explains.
CREATE TABLE inventory_logs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  product_id INT NOT NULL,
  quantity_change INT NOT NULL,
  reason VARCHAR(255) NOT NULL DEFAULT 'manual update',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_inventory_logs_product_created (product_id, created_at),
  FOREIGN KEY (product_id) REFERENCES products(id)
);

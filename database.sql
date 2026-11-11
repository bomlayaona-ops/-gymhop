-- ============================================================
-- GymHop database schema  (Phase 0 / v1)
-- Import in phpMyAdmin: Import tab -> choose this file -> Go
-- ============================================================
CREATE DATABASE IF NOT EXISTS gymhop_marketplace
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE gymhop_marketplace;

SET FOREIGN_KEY_CHECKS = 0;

-- ---------- USERS (one login table, role decides the dashboard) ----------
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(150) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('customer','admin','superadmin') NOT NULL,
  is_verified TINYINT(1) NOT NULL DEFAULT 0,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  profile_photo VARCHAR(255) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_users_role (role)
) ENGINE=InnoDB;

CREATE TABLE customer_profiles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE,
  first_name VARCHAR(60) NOT NULL,
  middle_name VARCHAR(60) NULL,
  last_name VARCHAR(60) NOT NULL,
  date_of_birth DATE NOT NULL,
  contact_number VARCHAR(20) NOT NULL,
  address VARCHAR(255) NOT NULL,
  profile_image VARCHAR(255) NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- GYMS ----------
CREATE TABLE gyms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(120) NOT NULL,
  slug VARCHAR(140) NOT NULL UNIQUE,
  description TEXT,
  logo VARCHAR(255) NULL,
  cover_photo VARCHAR(255) NULL,
  address VARCHAR(255) NOT NULL,
  city VARCHAR(80),
  province VARCHAR(80),
  contact_number VARCHAR(20),
  email VARCHAR(150),
  operating_hours VARCHAR(255),
  facilities TEXT,
  equipment TEXT,
  rules TEXT,
  facebook_url VARCHAR(255),
  instagram_url VARCHAR(255),
  is_open TINYINT(1) NOT NULL DEFAULT 1,           -- availability set by admin
  approval_status ENUM('draft','pending','approved','rejected') NOT NULL DEFAULT 'approved',
  rejection_reason VARCHAR(255) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_gyms_city (city),
  INDEX idx_gyms_status (approval_status)
) ENGINE=InnoDB;

CREATE TABLE admin_profiles (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL UNIQUE,
  gym_id INT NOT NULL,                              -- RULE 1: every admin linked to a gym
  first_name VARCHAR(60) NOT NULL,
  last_name VARCHAR(60) NOT NULL,
  contact_number VARCHAR(20) NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE gym_locations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  gym_id INT NOT NULL UNIQUE,
  latitude DECIMAL(10,7) NOT NULL,
  longitude DECIMAL(10,7) NOT NULL,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE gym_images (
  id INT AUTO_INCREMENT PRIMARY KEY,
  gym_id INT NOT NULL,
  image_path VARCHAR(255) NOT NULL,
  caption VARCHAR(150),
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE,
  INDEX idx_gym_images_gym (gym_id)
) ENGINE=InnoDB;

-- ---------- PRODUCTS ----------
CREATE TABLE product_categories (
  id INT AUTO_INCREMENT PRIMARY KEY,
  gym_id INT NOT NULL,
  name VARCHAR(80) NOT NULL,
  UNIQUE KEY uq_cat_gym_name (gym_id, name),
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  gym_id INT NOT NULL,
  category_id INT NULL,
  name VARCHAR(150) NOT NULL,
  description TEXT,
  price DECIMAL(10,2) NOT NULL,
  stock INT NOT NULL DEFAULT 0,
  image VARCHAR(255) NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE,
  FOREIGN KEY (category_id) REFERENCES product_categories(id) ON DELETE SET NULL,
  INDEX idx_products_gym (gym_id),
  INDEX idx_products_name (name)
) ENGINE=InnoDB;

-- ---------- MEMBERSHIPS ----------
CREATE TABLE membership_plans (
  id INT AUTO_INCREMENT PRIMARY KEY,
  gym_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  description TEXT,
  price DECIMAL(10,2) NOT NULL,
  duration_days INT NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE,
  INDEX idx_plans_gym (gym_id)
) ENGINE=InnoDB;

CREATE TABLE memberships (          -- a customer's subscription / application
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,          -- users.id
  gym_id INT NOT NULL,
  plan_id INT NOT NULL,
  status ENUM('pending','active','expired','rejected','cancelled') NOT NULL DEFAULT 'pending',
  start_date DATE NULL,
  end_date DATE NULL,
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE,
  FOREIGN KEY (plan_id) REFERENCES membership_plans(id) ON DELETE RESTRICT,
  INDEX idx_memberships_gym_status (gym_id, status),
  INDEX idx_memberships_customer (customer_id)
) ENGINE=InnoDB;

-- ---------- TRAINERS ----------
CREATE TABLE trainers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  gym_id INT NOT NULL,
  full_name VARCHAR(120) NOT NULL,
  profile_image VARCHAR(255) NULL,
  specialization VARCHAR(120),
  experience_years INT DEFAULT 0,
  description TEXT,
  rate_per_session DECIMAL(10,2) NOT NULL,
  availability VARCHAR(255),         -- e.g. "Mon-Fri 6AM-12PM"
  is_available TINYINT(1) NOT NULL DEFAULT 1,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE,
  INDEX idx_trainers_gym (gym_id)
) ENGINE=InnoDB;

CREATE TABLE trainer_bookings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  trainer_id INT NOT NULL,
  gym_id INT NOT NULL,
  session_date DATE NOT NULL,
  session_time TIME NOT NULL,
  status ENUM('pending','confirmed','completed','cancelled') NOT NULL DEFAULT 'pending',
  notes VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (trainer_id) REFERENCES trainers(id) ON DELETE CASCADE,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE,
  UNIQUE KEY uq_trainer_slot (trainer_id, session_date, session_time),
  INDEX idx_bookings_gym (gym_id)
) ENGINE=InnoDB;

-- ---------- CART ----------
CREATE TABLE carts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL UNIQUE,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE cart_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  cart_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL DEFAULT 1,
  UNIQUE KEY uq_cart_product (cart_id, product_id),
  FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---------- ORDERS ----------
-- One checkout can contain several gyms; it is split into one order PER GYM
-- so every sale is linked to the correct gym (RULE 6).
CREATE TABLE product_orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_number VARCHAR(30) NOT NULL UNIQUE,
  customer_id INT NOT NULL,
  gym_id INT NOT NULL,
  total_amount DECIMAL(10,2) NOT NULL,
  status ENUM('pending','processing','ready','completed','cancelled') NOT NULL DEFAULT 'pending',
  shipping_address VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE,
  INDEX idx_orders_gym_status (gym_id, status),
  INDEX idx_orders_customer (customer_id)
) ENGINE=InnoDB;

CREATE TABLE order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  product_name VARCHAR(150) NOT NULL,   -- snapshot at time of purchase
  unit_price DECIMAL(10,2) NOT NULL,
  quantity INT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES product_orders(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ---------- PAYMENTS ----------
-- A payment belongs to exactly ONE of: an order, a membership, or a booking (RULE 7).
-- Each gym adds its own payment QR codes (GCash, Maya, PayMongo, MariBank) that customers see when paying
CREATE TABLE IF NOT EXISTS gym_payment_methods (
  id INT AUTO_INCREMENT PRIMARY KEY,
  gym_id INT NOT NULL,
  method ENUM('gcash','maya','paymongo','maribank') NOT NULL,
  account_name VARCHAR(120) NULL,
  account_number VARCHAR(40) NULL,
  description VARCHAR(300) NULL,
  qr_image VARCHAR(255) NULL,
  is_enabled TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_gym_method (gym_id, method),
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE
);

CREATE TABLE payments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  reference_no VARCHAR(40) NOT NULL UNIQUE,      -- GymHop transaction reference
  customer_id INT NOT NULL,
  gym_id INT NOT NULL,
  order_id INT NULL,
  membership_id INT NULL,
  booking_id INT NULL,
  amount DECIMAL(10,2) NOT NULL,
  method ENUM('gcash','maya','cash_onsite','paymongo','maribank','other') NOT NULL,
  external_reference VARCHAR(80) NULL,           -- GCash/Maya ref number typed by customer
  proof_image VARCHAR(255) NULL,
  status ENUM('pending','paid','failed','cancelled','refunded') NOT NULL DEFAULT 'pending',
  verified_by INT NULL,                          -- admin user who confirmed it
  verified_at DATETIME NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE,
  FOREIGN KEY (order_id) REFERENCES product_orders(id) ON DELETE SET NULL,
  FOREIGN KEY (membership_id) REFERENCES memberships(id) ON DELETE SET NULL,
  FOREIGN KEY (booking_id) REFERENCES trainer_bookings(id) ON DELETE SET NULL,
  FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL,
  INDEX idx_payments_gym_status (gym_id, status),
  CONSTRAINT chk_one_target CHECK (
    (order_id IS NOT NULL) + (membership_id IS NOT NULL) + (booking_id IS NOT NULL) = 1)
) ENGINE=InnoDB;

-- Ledger of money movements (paid / refunded) used by Sales and Reports.
CREATE TABLE transactions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  payment_id INT NOT NULL,
  gym_id INT NOT NULL,
  type ENUM('sale','refund') NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  category ENUM('product','membership','training') NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE,
  INDEX idx_tx_gym_date (gym_id, created_at)
) ENGINE=InnoDB;

-- ---------- REVIEWS / FAVORITES / NOTIFICATIONS ----------
CREATE TABLE reviews (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  gym_id INT NOT NULL,
  product_id INT NULL,                -- NULL = review of the gym itself
  rating TINYINT NOT NULL,
  comment TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  CONSTRAINT chk_rating CHECK (rating BETWEEN 1 AND 5),
  INDEX idx_reviews_gym (gym_id)
) ENGINE=InnoDB;

CREATE TABLE favorites (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  gym_id INT NOT NULL,
  UNIQUE KEY uq_fav (customer_id, gym_id),
  FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (gym_id) REFERENCES gyms(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE notifications (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  title VARCHAR(150) NOT NULL,
  message VARCHAR(255) NOT NULL,
  link VARCHAR(255) NULL,
  is_read TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_notif_user_read (user_id, is_read)
) ENGINE=InnoDB;

-- ---------- EMAIL VERIFICATION / PASSWORD RESET ----------
CREATE TABLE email_verification_tokens (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  token_hash CHAR(64) NOT NULL UNIQUE,   -- SHA-256 of the emailed token
  expires_at DATETIME NOT NULL,
  used_at DATETIME NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE password_reset_tokens (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  token_hash CHAR(64) NOT NULL UNIQUE,
  expires_at DATETIME NOT NULL,
  used_at DATETIME NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

SET FOREIGN_KEY_CHECKS = 1;

-- No login accounts are inserted here on purpose (no hardcoded credentials).
-- The platform superadmin (who approves gyms) is created with: python create_superadmin.py

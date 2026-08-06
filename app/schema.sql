DROP TABLE IF EXISTS inventory_adjustments;
DROP TABLE IF EXISTS inventory_items;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS stores;
DROP TABLE IF EXISTS settings;

CREATE TABLE stores (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL COLLATE NOCASE UNIQUE, address TEXT, display_order INTEGER NOT NULL DEFAULT 0, is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN(0,1)), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL COLLATE NOCASE UNIQUE, display_order INTEGER NOT NULL DEFAULT 0);
CREATE TABLE inventory_items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL COLLATE NOCASE, quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0), unit TEXT NOT NULL DEFAULT 'item', store_id INTEGER NOT NULL, category_id INTEGER, restock_threshold INTEGER CHECK(restock_threshold IS NULL OR restock_threshold >= 0), target_quantity INTEGER CHECK(target_quantity IS NULL OR target_quantity >= 0), aisle TEXT, notes TEXT, is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN(0,1)), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(store_id) REFERENCES stores(id) ON DELETE RESTRICT, FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL, UNIQUE(name, store_id));
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE inventory_adjustments (id INTEGER PRIMARY KEY AUTOINCREMENT, inventory_item_id INTEGER NOT NULL, previous_quantity INTEGER NOT NULL, new_quantity INTEGER NOT NULL, change_amount INTEGER NOT NULL, reason TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(inventory_item_id) REFERENCES inventory_items(id) ON DELETE CASCADE);
CREATE INDEX idx_inventory_name ON inventory_items(name); CREATE INDEX idx_inventory_store ON inventory_items(store_id); CREATE INDEX idx_inventory_active_quantity ON inventory_items(is_active, quantity);
INSERT INTO settings(key,value) VALUES ('restock_threshold','1'),('default_target_quantity','3'),('theme','light'),('items_per_page','25'),('pdf_show_current_quantity','true'),('pdf_show_purchase_quantity','true');


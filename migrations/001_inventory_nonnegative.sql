-- MySQL 8.0.16+. Back up and resolve negative rows before applying.
ALTER TABLE inventory
  ADD CONSTRAINT ck_inventory_nonnegative CHECK (quantity >= 0);

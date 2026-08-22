-- Seed data for Eton WMS Local Development & Testing (MySQL & H2 Compatible)
--
-- Re-runnable: the deletes below clear what this file owns, so loading it twice is safe. Without
-- them the seller insert fails on a duplicate primary key and the rest of the file never applies.
DELETE FROM orders     WHERE order_number LIKE 'SO-ETON-%';
DELETE FROM credential WHERE seller_id = 1;
DELETE FROM user       WHERE user_id = 1;
DELETE FROM seller     WHERE seller_id = 1;

-- 1. Seller Record
INSERT INTO seller (seller_id, archived, created_date, updated_date, application_tag, currency, is_multi_warehouse, seller_code, selluseller_seller_id)
VALUES (1, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'DEFAULT', 'VND', false, 'SSIN10000007004', 7004);

-- 2. User Record
INSERT INTO user (user_id, archived, created_date, updated_date, auth_token, email, selluseller_user_id, seller_id)
VALUES (1, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'test_token', 'admin@anchanto.com', 7004, 1);

-- 3. Eton Credentials
INSERT INTO credential (credential_id, archived, created_date, updated_date, carrier_code, key_name, key_value, marketplace_code, wms_code, seller_id)
VALUES 
  (1, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, null, 'client_id', 'dummy_client_id', null, 'eton', 1),
  (2, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, null, 'client_secret', 'dummy_client_secret', null, 'eton', 1),
  (3, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, null, 'secret_code', 'dummy_secret_code', null, 'eton', 1),
  (4, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, null, 'warehouse_code', 'eton', null, 'eton', 1);

-- 4. Pre-seeded Packed Order (for testing HTTP 400 Bad Request / Order Already Packed scenario)
INSERT INTO orders (archived, created_date, updated_date, order_number, seller_id, selluseller_order_id, selluseller_store_id, warehouse_code, wms_order_id, status)
VALUES (false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SO-ETON-PACKED-001', 1, 9999400, 16643, 'eton', 'ETON_PACKED_001', 'NEW');

-- 5. Pricing cases (IA-5266) -- the priceDetail push that follows sale-order creation.
--
-- The cancellation cases need their order present locally: cancelOrder checks the order exists for
-- this seller and warehouse before calling Eton, and returns early if it does not.
--
-- SO-ETON-PRICING-001      cancellation cases 8 and 9 (partial re-creation, then full cancellation).
-- SO-ETON-PRICING-KIT-001  case 12, the partial cancellation whose surviving line is a kit.
-- SO-ETON-EXISTS-001       case 7, the replay. Already carries a wms_order_id, so the run finds it
--                          in the DB and does not save it again; the mock answers the creation with
--                          400 / BESO05 because the order number contains EXISTS, and that 400
--                          counts as success, leaving the pricing push as the only call that
--                          reaches Eton.
INSERT INTO orders (archived, created_date, updated_date, order_number, seller_id, selluseller_order_id, selluseller_store_id, warehouse_code, wms_order_id, status)
VALUES
  (false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SO-ETON-PRICING-001', 1, 9100001, 16643, 'eton', 'ETON_WMS_ORDER_001', 'NEW'),
  (false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SO-ETON-PRICING-KIT-001', 1, 9100002, 16643, 'eton', 'ETON_WMS_ORDER_001', 'NEW'),
  (false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SO-ETON-EXISTS-001', 1, 9100009, 16643, 'eton', 'ETON_WMS_ORDER_001', 'NEW');

-- The Lazada and TikTok create cases (2, 3, 4) need no seed row: createOrder writes the order
-- itself once Eton accepts it. Delete these rows between runs if you want a clean slate:
--   DELETE FROM orders WHERE order_number LIKE 'SO-ETON-PRICING%' OR order_number LIKE 'SO-ETON-EXISTS%';

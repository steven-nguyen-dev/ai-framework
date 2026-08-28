-- Fixtures the DPD UK createOrder flow reads before it can call DPD at all.
--
-- Load into the schema the app itself is pointed at. carrier-core's application-core-local.properties
-- says carrier_integrations_test, and ddl-auto is none, so nothing here is created by the app:
--
--   export MYSQL_PWD=$(grep '^MYSQL_PASSWORD=' docker/.env | cut -d= -f2-)
--   docker exec -i -e MYSQL_PWD="$MYSQL_PWD" mysql \
--     mysql -u jpluger carrier_integrations_test \
--     < dpd-uk/seed-data/dpd_uk_local_seed_data.sql
--
-- Re-runnable. Table definitions match the entities in
-- integration-standard/integration-standard-carrier-orm (CSeller, CCredential, CDispatchTimeSlots,
-- COrders) under Spring Boot's camel-case-to-underscores naming, which is what an app started with
-- ddl-auto=update would have created.

CREATE TABLE IF NOT EXISTS cseller (
    seller_id               BIGINT       NOT NULL AUTO_INCREMENT,
    currency                VARCHAR(255) NULL,
    seller_code             VARCHAR(255) NULL,
    selluseller_seller_id   INT          NOT NULL,
    country_code            VARCHAR(255) NULL,
    created_date            DATETIME     NULL,
    updated_date            DATETIME     NULL,
    archived                BIT(1)       NULL DEFAULT 0,
    PRIMARY KEY (seller_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS ccredential (
    credential_id  BIGINT        NOT NULL AUTO_INCREMENT,
    key_name       VARCHAR(255)  NULL,
    key_value      VARCHAR(2048) NULL,
    carrier_code   VARCHAR(255)  NULL,
    seller_id      BIGINT        NOT NULL,
    created_date   DATETIME      NULL,
    updated_date   DATETIME      NULL,
    archived       BIT(1)        NULL DEFAULT 0,
    PRIMARY KEY (credential_id),
    KEY ccredential_seller (seller_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS cdispatch_time_slots (
    slot_id       BIGINT       NOT NULL AUTO_INCREMENT,
    start_time    INT          NOT NULL,
    end_time      INT          NOT NULL,
    next_slot     INT          NOT NULL,
    slot_no       INT          NOT NULL,
    carrier_code  VARCHAR(255) NULL,
    next_day      BIT(1)       NULL DEFAULT 0,
    seller_id     BIGINT       NOT NULL,
    created_date  DATETIME     NULL,
    updated_date  DATETIME     NULL,
    archived      BIT(1)       NULL DEFAULT 0,
    PRIMARY KEY (slot_id),
    KEY cdispatch_seller (seller_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS corders (
    order_id                  BIGINT       NOT NULL AUTO_INCREMENT,
    selluseller_order_id      BIGINT       NULL,
    order_number              VARCHAR(255) NULL,
    order_date                VARCHAR(255) NULL,
    tracking_id               VARCHAR(255) NULL,
    courier_code              VARCHAR(255) NULL,
    courier_status            VARCHAR(255) NULL,
    carrier_status            VARCHAR(255) NULL,
    signature                 VARCHAR(255) NULL,
    shipment_id               BIGINT       NULL,
    shipment_number           VARCHAR(255) NULL,
    carrier_order_reference   VARCHAR(255) NULL,
    seller_id                 BIGINT       NOT NULL,
    created_date              DATETIME     NULL,
    updated_date              DATETIME     NULL,
    archived                  BIT(1)       NULL DEFAULT 0,
    PRIMARY KEY (order_id),
    KEY corders_seller (seller_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- The seller the suite fires as. event_parameters.seller_id is the selluseller id, and
-- CarriersCustomORM.getSeller looks the row up by it; every credential and time slot hangs off the
-- internal seller_id instead.
INSERT INTO cseller (seller_id, currency, seller_code, selluseller_seller_id, country_code,
                     created_date, updated_date, archived)
VALUES (1, 'GBP', 'RPTH', 42, 'GB', NOW(), NOW(), 0)
ON DUPLICATE KEY UPDATE seller_code = VALUES(seller_code),
                        selluseller_seller_id = VALUES(selluseller_seller_id),
                        country_code = VALUES(country_code),
                        archived = 0;

-- Basic auth for DPD. EParameterType.getEnum throws on any other key_name, and the throw is
-- swallowed, so a row named anything but username or password loses the whole credential set and
-- the shipment fails with no GeoSession.
DELETE FROM ccredential WHERE seller_id = 1 AND carrier_code IN ('dpd_uk', 'dpd_local');
INSERT INTO ccredential (credential_id, key_name, key_value, carrier_code, seller_id,
                         created_date, updated_date, archived)
VALUES (1, 'username', 'LOCAL_DPD_USER', 'dpd_uk',    1, NOW(), NOW(), 0),
       (2, 'password', 'LOCAL_DPD_PASS', 'dpd_uk',    1, NOW(), NOW(), 0),
       (3, 'username', 'LOCAL_DPD_USER', 'dpd_local', 1, NOW(), NOW(), 0),
       (4, 'password', 'LOCAL_DPD_PASS', 'dpd_local', 1, NOW(), NOW(), 0);

-- The collection slot. DpdUKUtility.collectionDateMapping counts seconds from midnight to
-- data.order_date_in_smp_timezone and asks for the slot holding that instant; a fixture dated any
-- other day gives a count far outside a real slot, and the row that is not found is dereferenced
-- straight away. One slot spanning everything is what makes a fixed test date usable: the answer is
-- always today 09:00 local.
DELETE FROM cdispatch_time_slots WHERE seller_id = 1 AND carrier_code IN ('dpd_uk', 'dpd_local');
INSERT INTO cdispatch_time_slots (slot_id, start_time, end_time, next_slot, slot_no, carrier_code,
                                  next_day, seller_id, created_date, updated_date, archived)
VALUES (1, -2000000000, 2000000000, 32400, 1, 'dpd_uk',    0, 1, NOW(), NOW(), 0),
       (2, -2000000000, 2000000000, 32400, 1, 'dpd_local', 0, 1, NOW(), NOW(), 0);

-- ============================================================================
--  RK TRENDZ :: 0007 — E-COMMERCE STORE + MLM INTEGRATION
--  Idempotent. Additive only. Existing data preserved.
-- ----------------------------------------------------------------------------
--  Business change: members no longer buy a company-chosen "package". They
--  shop products across 4 categories (Electrical, Clothes, Footwear, General)
--  and build a cart. When the cart total EXACTLY matches a plan tier amount
--  (1800 / 3600 / 7200 / 14400 / 28800) the plan activates (or upgrades) and
--  ALL plan benefits apply (self cashback, direct referral, level income,
--  rank progress). Later orders of any amount are REPURCHASES (repurchase
--  cashback + repurchase referral + business volume).
--
--  `orders` remains the single FINANCIAL anchor (revenue / COGS / GST /
--  commissions / rank volume). Shop orders link to it via orders.shop_order_id
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 0. Store settings (soft-coded, admin editable)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.store_settings (
    setting_key   VARCHAR(60) PRIMARY KEY,
    setting_value TEXT NOT NULL,
    description   TEXT,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO public.store_settings (setting_key, setting_value, description) VALUES
 ('activation_match_mode', 'exact', 'exact = cart must equal a plan amount to activate/upgrade; floor = highest plan reached'),
 ('shipping_fee',          '0',     'Flat shipping fee (INR) added at checkout'),
 ('free_shipping_above',   '0',     'Order subtotal above which shipping is free (0 = always apply shipping_fee)'),
 ('prices_include_gst',    'true',  'true = product prices are GST inclusive (Indian B2C default)'),
 ('store_name',            'RK Trendz Store', 'Storefront title'),
 ('min_repurchase_amount', '0',     'Minimum cart subtotal for a repurchase order by an active member')
ON CONFLICT (setting_key) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 1. Categories (the 4 business categories)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.product_categories (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    slug        VARCHAR(120) NOT NULL UNIQUE,
    description TEXT,
    image_url   TEXT,
    icon        VARCHAR(40),
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO public.product_categories (name, slug, description, icon, sort_order) VALUES
 ('Electrical',       'electrical',       'Fans, lights, appliances and electrical accessories', 'zap',    1),
 ('Clothes',          'clothes',          'Men, women and kids apparel',                          'shirt',  2),
 ('Footwear',         'footwear',         'Shoes, sandals and slippers',                          'footprints', 3),
 ('General Products', 'general-products', 'Home, kitchen, travel and daily-use products',         'package', 4)
ON CONFLICT (slug) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 2. Products / variants / images
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.products (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_id  BIGINT NOT NULL REFERENCES public.product_categories(id),
    name         VARCHAR(200) NOT NULL,
    slug         VARCHAR(220) NOT NULL UNIQUE,
    brand        VARCHAR(100),
    description  TEXT,
    highlights   TEXT,                       -- newline separated bullet points
    gst_percent  NUMERIC(5,2) NOT NULL DEFAULT 18,
    hsn_code     VARCHAR(20),
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    is_featured  BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_products_cat_active ON public.products (category_id, is_active);
CREATE INDEX IF NOT EXISTS idx_products_created    ON public.products (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_products_name_trgm  ON public.products USING GIN (name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS public.product_variants (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id   BIGINT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    sku          VARCHAR(80) NOT NULL UNIQUE,
    attributes   JSONB NOT NULL DEFAULT '{}'::jsonb,     -- {"size":"M","color":"Blue"}
    price        NUMERIC(12,2) NOT NULL,                  -- selling price (GST inclusive)
    mrp          NUMERIC(12,2),                           -- list price for strike-through
    cost_price   NUMERIC(12,2) NOT NULL DEFAULT 0,        -- actual product cost (COGS)
    stock_qty    INTEGER NOT NULL DEFAULT 0,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_variant_price_pos CHECK (price >= 0),
    CONSTRAINT chk_variant_stock_pos CHECK (stock_qty >= 0)
);
CREATE INDEX IF NOT EXISTS idx_variants_product ON public.product_variants (product_id, is_active);

CREATE TABLE IF NOT EXISTS public.product_images (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id  BIGINT NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    variant_id  BIGINT REFERENCES public.product_variants(id) ON DELETE SET NULL,
    image_url   TEXT NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_product_images_product ON public.product_images (product_id, sort_order);

-- ---------------------------------------------------------------------------
-- 3. Carts
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.carts (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS public.cart_items (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cart_id    BIGINT NOT NULL REFERENCES public.carts(id) ON DELETE CASCADE,
    variant_id BIGINT NOT NULL REFERENCES public.product_variants(id) ON DELETE CASCADE,
    qty        INTEGER NOT NULL CHECK (qty > 0),
    added_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (cart_id, variant_id)
);

-- ---------------------------------------------------------------------------
-- 4. Addresses
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_addresses (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    full_name  VARCHAR(150) NOT NULL,
    phone      VARCHAR(20)  NOT NULL,
    line1      VARCHAR(200) NOT NULL,
    line2      VARCHAR(200),
    landmark   VARCHAR(120),
    city       VARCHAR(80)  NOT NULL,
    state      VARCHAR(80)  NOT NULL,
    pincode    VARCHAR(12)  NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user_addresses_user ON public.user_addresses (user_id);

-- ---------------------------------------------------------------------------
-- 5. Shop orders (fulfilment) — money truth still lives in `orders`
-- ---------------------------------------------------------------------------
CREATE SEQUENCE IF NOT EXISTS public.shop_order_no_seq START 1001;

CREATE TABLE IF NOT EXISTS public.shop_orders (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_no           VARCHAR(30) NOT NULL UNIQUE,
    user_id            BIGINT NOT NULL REFERENCES public.users(id),
    subtotal           NUMERIC(12,2) NOT NULL,          -- items total (GST inclusive)
    gst_amount         NUMERIC(12,2) NOT NULL DEFAULT 0,-- GST contained in subtotal
    shipping_fee       NUMERIC(12,2) NOT NULL DEFAULT 0,
    discount           NUMERIC(12,2) NOT NULL DEFAULT 0,
    total              NUMERIC(12,2) NOT NULL,          -- subtotal - discount + shipping
    cost_total         NUMERIC(12,2) NOT NULL DEFAULT 0,-- COGS of items
    order_kind         VARCHAR(20) NOT NULL DEFAULT 'repurchase', -- activation|upgrade|repurchase
    plan_id            INTEGER,                         -- matched plan (activation/upgrade)
    payment_method     VARCHAR(20) NOT NULL,            -- wallet|online|split
    payment_status     VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending|paid|failed|refunded|review
    order_status       VARCHAR(20) NOT NULL DEFAULT 'placed',  -- placed|confirmed|packed|shipped|delivered|cancelled
    wallet_paid        NUMERIC(12,2) NOT NULL DEFAULT 0,
    online_paid        NUMERIC(12,2) NOT NULL DEFAULT 0,
    gateway            VARCHAR(20),
    gateway_order_id   VARCHAR(80),
    gateway_payment_id VARCHAR(80),
    shipping_address   JSONB,
    courier            VARCHAR(80),
    tracking_no        VARCHAR(80),
    customer_note      TEXT,
    admin_note         TEXT,
    mlm_order_id       BIGINT,                          -- -> orders.id once paid
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    paid_at            TIMESTAMP,
    shipped_at         TIMESTAMP,
    delivered_at       TIMESTAMP,
    cancelled_at       TIMESTAMP,
    updated_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_shop_orders_user    ON public.shop_orders (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_shop_orders_status  ON public.shop_orders (order_status, payment_status);
CREATE INDEX IF NOT EXISTS idx_shop_orders_gateway ON public.shop_orders (gateway_order_id);
CREATE INDEX IF NOT EXISTS idx_shop_orders_created ON public.shop_orders (created_at DESC);

CREATE TABLE IF NOT EXISTS public.shop_order_items (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id      BIGINT NOT NULL REFERENCES public.shop_orders(id) ON DELETE CASCADE,
    product_id    BIGINT,
    variant_id    BIGINT,
    product_name  VARCHAR(200) NOT NULL,
    variant_label VARCHAR(120),
    sku           VARCHAR(80),
    image_url     TEXT,
    qty           INTEGER NOT NULL CHECK (qty > 0),
    unit_price    NUMERIC(12,2) NOT NULL,
    unit_cost     NUMERIC(12,2) NOT NULL DEFAULT 0,
    gst_percent   NUMERIC(5,2)  NOT NULL DEFAULT 0,
    line_total    NUMERIC(12,2) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shop_order_items_order ON public.shop_order_items (order_id);

CREATE TABLE IF NOT EXISTS public.shop_order_events (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id   BIGINT NOT NULL REFERENCES public.shop_orders(id) ON DELETE CASCADE,
    status     VARCHAR(30) NOT NULL,
    note       TEXT,
    actor      VARCHAR(30) NOT NULL DEFAULT 'system',   -- system|member|admin:<id>
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_shop_order_events_order ON public.shop_order_events (order_id, created_at);

-- ---------------------------------------------------------------------------
-- 6. `orders` becomes the universal financial anchor
-- ---------------------------------------------------------------------------
ALTER TABLE public.orders ALTER COLUMN package_id DROP NOT NULL;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS shop_order_id BIGINT;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS cost_amount   NUMERIC(12,2) NOT NULL DEFAULT 0;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS gst_amount    NUMERIC(12,2) NOT NULL DEFAULT 0;
ALTER TABLE public.orders ADD COLUMN IF NOT EXISTS order_kind    VARCHAR(20) NOT NULL DEFAULT 'activation';
CREATE INDEX IF NOT EXISTS idx_orders_status ON public.orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_shop   ON public.orders (shop_order_id);

-- Back-fill COGS for legacy plan orders from the plan's product cost.
UPDATE public.orders o
SET cost_amount = sp.product_cost
FROM public.subscription_plans sp
WHERE sp.id = o.package_id AND o.cost_amount = 0 AND sp.product_cost > 0;

-- ---------------------------------------------------------------------------
-- 7. RANK FIX: nobody holds a rank until BOTH targets are met.
--    (rank_level defaulted to 1 = "Bronze" for every new user — wrong.)
-- ---------------------------------------------------------------------------
ALTER TABLE public.users ALTER COLUMN rank_level SET DEFAULT 0;
UPDATE public.users u
SET rank_level = COALESCE((
    SELECT MAX(r.level) FROM public.rank_rules r
    WHERE r.req_team_size <= COALESCE(u.total_team_count, 0)
      AND r.req_business_vol <= (
            SELECT COALESCE(SUM(o.amount), 0)
            FROM public.orders o JOIN public.users d ON d.id = o.user_id
            WHERE d.tree_path <@ u.tree_path AND o.status = 'completed')
), 0)
WHERE u.tree_path IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 8. Sample catalogue so the store works on day one (admin can edit/delete).
--    Prices are chosen so carts can hit the plan tiers exactly.
-- ---------------------------------------------------------------------------
DO $seed$
DECLARE
    c_el BIGINT; c_cl BIGINT; c_fw BIGINT; c_gp BIGINT; pid BIGINT;
BEGIN
    SELECT id INTO c_el FROM public.product_categories WHERE slug='electrical';
    SELECT id INTO c_cl FROM public.product_categories WHERE slug='clothes';
    SELECT id INTO c_fw FROM public.product_categories WHERE slug='footwear';
    SELECT id INTO c_gp FROM public.product_categories WHERE slug='general-products';

    IF NOT EXISTS (SELECT 1 FROM public.products LIMIT 1) THEN
        -- Electrical
        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code,is_featured)
        VALUES (c_el,'High-Speed Ceiling Fan 1200mm','ceiling-fan-1200mm','RK Electricals',
                'Energy-efficient 1200 mm ceiling fan with copper winding motor and anti-dust blades.',
                E'Copper winding motor\n380 RPM high air delivery\n2 year warranty',18,'8414',TRUE) RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'EL-FAN-WHT','{"color":"White"}',1800,2400,1150,50),
          (pid,'EL-FAN-BRN','{"color":"Brown"}',1800,2400,1150,50);
        INSERT INTO public.product_images (product_id,image_url,sort_order) VALUES (pid,'/static/uploads/products/sample-ceiling-fan.jpg',0);

        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code)
        VALUES (c_el,'LED Bulb 9W Cool Daylight (Pack of 4)','led-bulb-9w-pack-4','RK Electricals',
                'Long-life 9 W LED bulbs, 900 lumens each, B22 base.',E'900 lumens\n15000 hour life\nPack of 4',12,'8539') RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'EL-LED9-4','{}',450,600,260,200);
        INSERT INTO public.product_images (product_id,image_url,sort_order) VALUES (pid,'/static/uploads/products/sample-led-bulb.jpg',0);

        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code)
        VALUES (c_el,'Extension Board 4 Socket + 2 USB','extension-board-4-socket','RK Electricals',
                'Surge-protected 4 socket extension board with 2 m cable and 2 USB ports.',E'Surge protection\n2 m heavy duty cable\nISI marked',18,'8536') RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'EL-EXT4','{}',600,850,340,120);

        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code)
        VALUES (c_el,'Electric Kettle 1.5 L','electric-kettle-1-5l','RK Electricals',
                'Stainless steel 1500 W electric kettle with auto cut-off.',E'1500 W fast boil\nAuto cut-off\nStainless steel body',18,'8516') RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'EL-KET15','{}',900,1250,520,80);

        -- Clothes
        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code,is_featured)
        VALUES (c_cl,'Men''s Premium Cotton T-Shirt','mens-premium-cotton-tshirt','RK Trendz Apparel',
                '100% combed cotton round-neck T-shirt, bio-washed for softness.',E'100% combed cotton\nBio-washed\nRegular fit',5,'6109',TRUE) RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'CL-TS-BLK-M','{"size":"M","color":"Black"}',450,799,210,60),
          (pid,'CL-TS-BLK-L','{"size":"L","color":"Black"}',450,799,210,60),
          (pid,'CL-TS-BLK-XL','{"size":"XL","color":"Black"}',450,799,210,40),
          (pid,'CL-TS-NVY-M','{"size":"M","color":"Navy"}',450,799,210,60),
          (pid,'CL-TS-NVY-L','{"size":"L","color":"Navy"}',450,799,210,60),
          (pid,'CL-TS-NVY-XL','{"size":"XL","color":"Navy"}',450,799,210,40);
        INSERT INTO public.product_images (product_id,image_url,sort_order) VALUES (pid,'/static/uploads/products/sample-tshirt.jpg',0);

        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code)
        VALUES (c_cl,'Women''s Printed Rayon Kurti','womens-printed-rayon-kurti','RK Trendz Apparel',
                'Straight-cut printed rayon kurti, 3/4 sleeves, knee length.',E'Soft rayon fabric\n3/4 sleeves\nMachine washable',5,'6204') RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'CL-KUR-S','{"size":"S"}',900,1499,430,40),
          (pid,'CL-KUR-M','{"size":"M"}',900,1499,430,60),
          (pid,'CL-KUR-L','{"size":"L"}',900,1499,430,60),
          (pid,'CL-KUR-XL','{"size":"XL"}',900,1499,430,40);
        INSERT INTO public.product_images (product_id,image_url,sort_order) VALUES (pid,'/static/uploads/products/sample-kurti.jpg',0);

        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code)
        VALUES (c_cl,'Men''s Slim Fit Stretch Denim Jeans','mens-slim-fit-denim-jeans','RK Trendz Apparel',
                'Mid-rise slim fit jeans with 2% stretch for all-day comfort.',E'Stretch denim\nSlim fit\n5 pocket styling',12,'6203') RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'CL-JN-30','{"size":"30"}',1200,1999,620,30),
          (pid,'CL-JN-32','{"size":"32"}',1200,1999,620,40),
          (pid,'CL-JN-34','{"size":"34"}',1200,1999,620,40),
          (pid,'CL-JN-36','{"size":"36"}',1200,1999,620,25);

        -- Footwear
        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code,is_featured)
        VALUES (c_fw,'Men''s Lightweight Running Shoes','mens-lightweight-running-shoes','RK Sports',
                'Breathable mesh running shoes with cushioned EVA sole.',E'Breathable mesh upper\nCushioned EVA sole\nAnti-skid grip',12,'6404',TRUE) RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'FW-RUN-7','{"size":"UK 7"}',1800,2999,950,30),
          (pid,'FW-RUN-8','{"size":"UK 8"}',1800,2999,950,40),
          (pid,'FW-RUN-9','{"size":"UK 9"}',1800,2999,950,40),
          (pid,'FW-RUN-10','{"size":"UK 10"}',1800,2999,950,25);
        INSERT INTO public.product_images (product_id,image_url,sort_order) VALUES (pid,'/static/uploads/products/sample-running-shoes.jpg',0);

        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code)
        VALUES (c_fw,'Casual Comfort Sandals','casual-comfort-sandals','RK Sports',
                'Soft footbed casual sandals with adjustable straps.',E'Soft footbed\nAdjustable straps\nDurable outsole',12,'6402') RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'FW-SAN-7','{"size":"UK 7"}',600,999,310,40),
          (pid,'FW-SAN-8','{"size":"UK 8"}',600,999,310,40),
          (pid,'FW-SAN-9','{"size":"UK 9"}',600,999,310,40),
          (pid,'FW-SAN-10','{"size":"UK 10"}',600,999,310,30);
        INSERT INTO public.product_images (product_id,image_url,sort_order) VALUES (pid,'/static/uploads/products/sample-sandals.jpg',0);

        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code)
        VALUES (c_fw,'Men''s Formal Leather Shoes','mens-formal-leather-shoes','RK Sports',
                'Classic lace-up formal shoes in genuine leather.',E'Genuine leather\nCushioned insole\nLace-up',18,'6403') RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'FW-FRM-7','{"size":"UK 7"}',900,1799,480,20),
          (pid,'FW-FRM-8','{"size":"UK 8"}',900,1799,480,30),
          (pid,'FW-FRM-9','{"size":"UK 9"}',900,1799,480,30),
          (pid,'FW-FRM-10','{"size":"UK 10"}',900,1799,480,20);

        -- General products
        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code)
        VALUES (c_gp,'Stainless Steel Water Bottle 1 L','stainless-steel-water-bottle-1l','RK Home',
                'Double-wall insulated bottle keeps drinks cold 24 h / hot 12 h.',E'Double wall insulation\nLeak-proof cap\nBPA free',18,'7323') RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'GP-BTL-SLV','{"color":"Silver"}',300,499,140,150),
          (pid,'GP-BTL-BLK','{"color":"Black"}',300,499,140,150);
        INSERT INTO public.product_images (product_id,image_url,sort_order) VALUES (pid,'/static/uploads/products/sample-water-bottle.jpg',0);

        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code)
        VALUES (c_gp,'Kitchen Storage Container Set (6 pcs)','kitchen-storage-set-6pcs','RK Home',
                'Air-tight BPA-free storage containers in 3 sizes, 2 each.',E'Air-tight lids\n6 pieces\nDishwasher safe',18,'3924') RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'GP-KIT6','{}',600,999,300,80);

        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code)
        VALUES (c_gp,'Cotton Double Bedsheet with 2 Pillow Covers','cotton-double-bedsheet','RK Home',
                '100% cotton 144 TC double bedsheet, 90 x 100 inch.',E'100% cotton\n144 thread count\nColour-fast print',5,'6304') RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'GP-BED-BLU','{"color":"Blue"}',900,1499,470,40),
          (pid,'GP-BED-GRN','{"color":"Green"}',900,1499,470,40);

        INSERT INTO public.products (category_id,name,slug,brand,description,highlights,gst_percent,hsn_code,is_featured)
        VALUES (c_gp,'Laptop Backpack 30 L Water Resistant','laptop-backpack-30l','RK Home',
                'Padded 15.6" laptop compartment, USB charging port, rain cover.',E'30 L capacity\nPadded laptop sleeve\nWater resistant',18,'4202',TRUE) RETURNING id INTO pid;
        INSERT INTO public.product_variants (product_id,sku,attributes,price,mrp,cost_price,stock_qty) VALUES
          (pid,'GP-BAG-BLK','{"color":"Black"}',1200,1999,610,60),
          (pid,'GP-BAG-GRY','{"color":"Grey"}',1200,1999,610,60);
        INSERT INTO public.product_images (product_id,image_url,sort_order) VALUES (pid,'/static/uploads/products/sample-backpack.jpg',0);
    END IF;
END
$seed$;

-- ===========================================================================
-- VERIFY:
--   SELECT c.name, COUNT(p.id) FROM product_categories c LEFT JOIN products p ON p.category_id=c.id GROUP BY 1;
--   SELECT id, rank_level FROM users ORDER BY id;
-- ===========================================================================

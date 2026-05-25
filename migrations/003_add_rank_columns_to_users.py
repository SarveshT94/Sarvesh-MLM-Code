from yoyo import step

# We use IF NOT EXISTS to prevent crashes if you ever run this twice
steps = [
    step(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS rank_level INT DEFAULT 1;",
        "ALTER TABLE users DROP COLUMN IF NOT EXISTS rank_level;"
    ),
    step(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS current_volume NUMERIC(15,2) DEFAULT 0.00;",
        "ALTER TABLE users DROP COLUMN IF NOT EXISTS current_volume;"
    )
]

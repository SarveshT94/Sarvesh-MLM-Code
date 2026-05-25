"""
create_company_settings
"""

from yoyo import step

__depends__ = {}

steps = [
    step(
        # FORWARD STEP: Create the table
        """
        CREATE TABLE IF NOT EXISTS company_settings (
            id SERIAL PRIMARY KEY,
            company_name VARCHAR(255),
            gst_number VARCHAR(50),
            logo_url VARCHAR(255),
            support_email VARCHAR(100),
            support_phone VARCHAR(50),
            head_office_address TEXT,
            branch_address TEXT,
            bank_name VARCHAR(100),
            account_holder_name VARCHAR(100),
            account_number VARCHAR(50),
            ifsc_code VARCHAR(20),
            upi_id VARCHAR(100),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        # ROLLBACK STEP: If we ever need to undo this migration
        "DROP TABLE IF EXISTS company_settings;"
    ),
    step(
        # Seed the database with a default row so your frontend doesn't crash
        """
        INSERT INTO company_settings (id, bank_name, account_holder_name, account_number, ifsc_code, upi_id)
        VALUES (1, 'Setup Required', 'Setup Required', '0000000000', 'XXXX0000000', 'yourname@upi')
        ON CONFLICT (id) DO NOTHING;
        """
    )
]
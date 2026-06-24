import pandas as pd
from dateutil import parser as date_parser
import uuid

REQUIRED_COLUMNS = {
    "txn_id", "date", "merchant", "amount", "currency",
    "status", "category", "account_id", "notes"
}


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

    # 1. Remove exact duplicate rows
    df = df.drop_duplicates().copy()

    # 2. Fill missing txn_id
    df['txn_id'] = df['txn_id'].apply(
        lambda x: x if pd.notna(x) and str(x).strip() != '' else str(uuid.uuid4())
    )

    # 3. Normalize date formats to ISO 8601
    def parse_date(val):
        try:
            return date_parser.parse(str(val), dayfirst=True).strftime('%Y-%m-%d')
        except:
            return None

    df['date'] = df['date'].apply(parse_date)

    # 4. Strip currency symbols from amount
    def clean_amount(val):
        try:
            cleaned = str(val).replace('$', '').replace(',', '').strip()
            if cleaned == '' or cleaned.lower() == 'nan':
                return None
            return float(cleaned)
        except:
            return None

    df['amount'] = df['amount'].apply(clean_amount)

    # 5. Uppercase currency and status
    df['currency'] = df['currency'].apply(
        lambda x: str(x).upper().strip() if pd.notna(x) else None
    )
    df['status'] = df['status'].apply(
        lambda x: str(x).upper().strip() if pd.notna(x) else None
    )

    # 6. Fill missing category
    df['category'] = df['category'].apply(
        lambda x: x if pd.notna(x) and str(x).strip() != '' else 'Uncategorised'
    )

    # 7. Strip whitespace from merchant
    df['merchant'] = df['merchant'].apply(
        lambda x: str(x).strip() if pd.notna(x) else None
    )
    df['account_id'] = df['account_id'].apply(
        lambda x: str(x).strip() if pd.notna(x) else None
    )
    df['notes'] = df['notes'].apply(
        lambda x: str(x).strip() if pd.notna(x) and str(x).strip() != '' else None
    )

    return df

# Minimal Portfolio Schema Proposal

This is a sanitized proposal for storing portfolio information and trading history in Neon/Postgres. It is a planning reference only and does not contain real account details, credentials, brokerage exports, or trading records.

## Scope

Initial scope:

- Store broker or exchange accounts.
- Store executed trades.
- Store cash movements such as deposits, withdrawals, dividends, interest, fees, taxes, and adjustments.
- Keep instrument normalization out of scope for now.

Later optional scope:

- Store periodic position snapshots for broker/API reconciliation.
- Add an `instruments` table if symbol metadata, corporate actions, derivatives, or cross-market normalization become difficult to manage inline.

## Design Notes

- Target database: Neon/Postgres.
- Use Postgres `numeric` for money, prices, and quantities.
- Use `timestamptz` for event timestamps.
- Use `date` for settlement dates.
- Store `symbol`, `market`, `asset_type`, and `currency` directly on trade and snapshot rows at first.
- Keep `source` and `external_id` fields for future CSV/API import deduplication.
- Do not store credentials, API keys, full account numbers, raw brokerage exports, tax documents, or full statements.

## Core Tables

### `accounts`

Stores broker or exchange accounts.

```sql
create table accounts (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  provider text,
  base_currency text not null default 'HKD',
  created_at timestamptz not null default now()
);
```

### `trades`

Stores executed buy and sell trades. Instrument details are kept inline for the first version.

```sql
create table trades (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references accounts(id),

  symbol text not null,
  market text,
  asset_type text not null,

  side text not null check (side in ('buy', 'sell')),
  quantity numeric not null check (quantity > 0),
  price numeric not null check (price >= 0),
  currency text not null,

  fees numeric not null default 0,
  taxes numeric not null default 0,
  net_amount numeric,

  traded_at timestamptz not null,
  settlement_date date,

  source text,
  external_id text,
  notes text,

  created_at timestamptz not null default now()
);
```

### `cash_movements`

Stores cash events that are not ordinary executed buy/sell trades.

```sql
create table cash_movements (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references accounts(id),

  currency text not null,
  amount numeric not null,
  movement_type text not null check (
    movement_type in (
      'deposit',
      'withdrawal',
      'dividend',
      'interest',
      'fee',
      'tax',
      'adjustment'
    )
  ),

  occurred_at timestamptz not null,
  settlement_date date,

  related_trade_id uuid references trades(id),
  source text,
  external_id text,
  notes text,

  created_at timestamptz not null default now()
);
```

## Optional Later Table

### `position_snapshots`

Stores periodic portfolio snapshots when reconciliation against broker/API data becomes useful.

```sql
create table position_snapshots (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references accounts(id),

  snapshot_date date not null,
  symbol text not null,
  market text,
  asset_type text not null,
  currency text not null,

  quantity numeric not null,
  avg_cost numeric,
  market_price numeric,
  market_value numeric,

  created_at timestamptz not null default now(),

  unique (account_id, snapshot_date, symbol, market)
);
```

## Suggested Indexes

```sql
create index trades_account_traded_at_idx
  on trades (account_id, traded_at desc);

create index trades_symbol_market_idx
  on trades (symbol, market);

create unique index trades_source_external_id_idx
  on trades (source, external_id)
  where source is not null and external_id is not null;

create index cash_movements_account_occurred_at_idx
  on cash_movements (account_id, occurred_at desc);

create unique index cash_movements_source_external_id_idx
  on cash_movements (source, external_id)
  where source is not null and external_id is not null;
```

## Neon Application Notes

- Confirm before applying any of this schema to Neon.
- If `gen_random_uuid()` is unavailable, enable the required Postgres extension or switch to another ID strategy before migration.
- Apply schema changes separately from data import.
- Import only sanitized or necessary records, and avoid storing raw brokerage exports in the database.

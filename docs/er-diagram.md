# Entity–Relationship Diagram

All tables use an internal surrogate integer PK (`id`). Google's own ids are
stored separately in `*_id` (BigInteger) columns. Snapshot tables are
append-only and carry `snapshot_date`, `sync_time`, `account_id`, `sync_log_id`.

## Dimension ↔ snapshot overview

```mermaid
erDiagram
    accounts {
      int id PK
      string customer_id UK "Google id, digits"
      string descriptive_name
      string currency_code
      string time_zone
      bool   is_manager
      string manager_customer_id
      bool   is_syncable
    }
    campaigns {
      int id PK
      int account_id FK
      bigint campaign_id "Google id"
      string name
      string status
      string bidding_strategy_type
      string networks
      date   start_date
      date   end_date
      float  optimization_score
      bigint budget_id "Google budget id"
    }
    ad_groups {
      int id PK
      int account_id FK
      int campaign_id FK
      bigint ad_group_id "Google id"
      string name
      string status
      string type
      bigint cpc_bid_micros
    }
    keywords {
      int id PK
      int account_id FK
      int ad_group_id FK
      bigint criterion_id "Google id"
      string text
      string match_type
      string status
    }
    ads {
      int id PK
      int account_id FK
      int ad_group_id FK
      bigint ad_id "Google id"
      string type
      string status
      string approval_status
      text   headlines
      text   descriptions
    }
    search_terms {
      int id PK
      int account_id FK
      int campaign_id FK
      int ad_group_id FK
      string query
      string match_type
    }
    budgets {
      int id PK
      int account_id FK
      bigint budget_id "Google id"
      bigint amount_micros
      string delivery_method
      string period
    }

    campaign_snapshots {
      int id PK
      int account_id FK
      int campaign_id FK
      date snapshot_date
      datetime sync_time
      bigint impressions
      bigint clicks
      bigint cost_micros
      numeric ctr
      bigint budget_micros
      float optimization_score
    }
    keyword_snapshots {
      int id PK
      int keyword_id FK
      date snapshot_date
      int  quality_score
      string expected_ctr
      string landing_page_experience
      string ad_relevance
      bigint impressions
      bigint clicks
      bigint cost_micros
    }
    sync_logs {
      int id PK
      string sync_type
      string entity
      string customer_id
      string status
      datetime started_at
      datetime finished_at
      bigint duration_ms
      int rows_inserted
      int rows_updated
      int rows_failed
      json details
    }

    accounts ||--o{ campaigns : ""
    accounts ||--o{ budgets : ""
    campaigns ||--o{ ad_groups : ""
    ad_groups ||--o{ keywords : ""
    ad_groups ||--o{ ads : ""
    ad_groups ||--o{ search_terms : ""
    campaigns ||--o{ campaign_snapshots : ""
    keywords  ||--o{ keyword_snapshots : ""
```

## Full table list

| Table | Kind | Notes |
|---|---|---|
| `accounts` | dimension | MCC + client accounts |
| `campaigns` | dimension | natural key `(account_id, campaign_id)` |
| `campaign_snapshots` | snapshot | daily metrics + config |
| `campaign_device_snapshots` | snapshot | per-device metrics |
| `campaign_geo_snapshots` | snapshot | per-country metrics |
| `ad_groups` | dimension | natural key `(campaign_id, ad_group_id)` |
| `ad_group_snapshots` | snapshot | daily metrics |
| `keywords` | dimension | natural key `(ad_group_id, criterion_id)` |
| `keyword_snapshots` | snapshot | daily metrics + Quality Score |
| `ads` | dimension | natural key `(ad_group_id, ad_id)` |
| `ad_snapshots` | snapshot | daily metrics + approval status |
| `search_terms` | dimension | natural key `(ad_group_id, query, match_type)` |
| `search_term_snapshots` | snapshot | daily metrics |
| `budgets` | dimension | natural key `(account_id, budget_id)` |
| `budget_snapshots` | snapshot | daily amount, spend, utilization |
| `recommendations` | snapshot | point-in-time active recommendations |
| `sync_logs` | operational | one per entity/account run |
| `api_tokens` | operational | Phase 2 per-tenant OAuth (encrypted) |
| `users` | operational | Phase 2 RBAC placeholder |

## Indexing

Snapshot tables are indexed on `snapshot_date`, `account_id`, `sync_time`, and
their entity FK, which covers the date-range + account scans the dashboard
aggregates perform. Dimension natural keys are enforced with unique constraints.

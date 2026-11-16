-- HomeSolarPH opt-in anonymous records. Apply once to the Postgres database.
-- No names, addresses, city/barangay, contact details, IP addresses, installer names or files are stored.

create table if not exists submission (
  id            uuid primary key default gen_random_uuid(),
  ref_code      text unique not null,
  kind          text not null check (kind in ('check','quotes')),
  submitted_ym  char(7) not null,
  consent_ver   text not null,
  app_ver       text not null
);

create table if not exists check_record (
  submission_id uuid primary key references submission(id) on delete cascade,
  region text, provider_type text, bill_php numeric, kwh_month numeric, kwh_estimated boolean,
  daytime_band text, home_type text, roof_type text, roof_area_band text,
  direction text, shading text, net_metering text, budget_band text,
  size_low numeric, size_high numeric, payback_low numeric, payback_high numeric
);

create table if not exists quote_record (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid references submission(id) on delete cascade,
  region text, system_type text, kwp numeric, total_price_php numeric, vat_included boolean,
  price_per_wp numeric, panel_brand text, panel_watt int, panel_qty int,
  inverter_brand text, inverter_type text, inverter_kw numeric,
  battery_brand text, battery_kwh numeric, mounting text,
  incl_net_metering boolean, incl_permits boolean, incl_electrical boolean,
  incl_monitoring boolean, incl_installation boolean, incl_after_sales boolean,
  w_panel_product int, w_panel_perf int, w_inverter int, w_battery int, w_workmanship int,
  deposit_pct numeric, timeline_weeks numeric, extraction_source text, fields_corrected int
);

create table if not exists feedback (
  id uuid primary key default gen_random_uuid(),
  page text, useful boolean, comment text, submitted_ym char(7)
);

create table if not exists ai_usage (day date primary key, calls int not null default 0);

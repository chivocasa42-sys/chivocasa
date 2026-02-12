-- =========================================================
-- 1) Nearest comparable listings
-- =========================================================
create or replace function public.avm_nearest_matches(
  p_lat double precision,
  p_lon double precision,
  p_area_m2 numeric,
  p_listing_type text,
  p_property_class text,
  p_bedrooms integer default null,
  p_bathrooms numeric default null,
  p_parking integer default null,
  p_subject_price numeric default null,
  p_min_comps integer default 8,
  p_limit integer default 20,
  p_max_age_days integer default 180,
  p_radius_ladder_m integer[] default array[1000, 2000, 3000, 5000, 8000, 12000, 20000]
)
returns table(
  match_mode text,
  selected_radius_m integer,
  comp_rank integer,
  comp_external_id text,
  comp_title text,
  comp_source text,
  comp_listing_type text,
  comp_property_class text,
  comp_price numeric,
  comp_area_m2 numeric,
  comp_price_m2 numeric,
  distance_m integer,
  days_old integer,
  comp_active boolean,
  comp_bedrooms integer,
  comp_bathrooms numeric,
  comp_parking integer,
  distance_weight numeric,
  freshness_weight numeric,
  status_weight numeric,
  size_weight numeric,
  feature_weight numeric,
  total_weight numeric,
  delta_vs_subject_ppm2_pct numeric,
  comp_url text
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_now timestamptz := now();
  v_geom geography;
  v_radius integer;
  v_count integer := 0;
  v_subject_ppm2 numeric;
  v_age_days integer := coalesce(p_max_age_days, 180);
  v_limit integer := greatest(1, coalesce(p_limit, 20));
  v_min_comps integer := greatest(1, coalesce(p_min_comps, 8));
  v_radius_ladder integer[] := coalesce(
    p_radius_ladder_m,
    array[1000, 2000, 3000, 5000, 8000, 12000, 20000]
  );
begin
  if p_lat is null or p_lon is null then
    raise exception using errcode = '22023', message = 'latitude and longitude are required';
  end if;

  if p_area_m2 is null or p_area_m2 <= 0 then
    raise exception using errcode = '22023', message = 'area_m2 is required and must be > 0';
  end if;

  if p_listing_type is null or btrim(p_listing_type) = '' then
    raise exception using errcode = '22023', message = 'listing_type is required';
  end if;

  if p_property_class is null or btrim(p_property_class) = '' then
    raise exception using errcode = '22023', message = 'property_class is required';
  end if;

  v_geom := ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography;
  v_subject_ppm2 := case
    when p_subject_price is not null and p_subject_price > 0 then p_subject_price / p_area_m2
    else null
  end;

  -- choose smallest radius that yields enough comps
  foreach v_radius in array v_radius_ladder
  loop
    with base as (
      select
        c.external_id::text as comp_id,
        c.price::numeric as price,
        nullif(regexp_replace(replace(coalesce(c.specs->>'area_m2', ''), ',', ''), '[^0-9\.\-]', '', 'g'), '')::numeric as area_m2,
        nullif(c.location->>'latitude', '')::double precision as lat,
        nullif(c.location->>'longitude', '')::double precision as lon
      from public.scrapped_data c
      where c.price is not null
        and c.price > 0
        and c.listing_type = p_listing_type
        and coalesce(c.last_updated, c.published_date::timestamptz) >= v_now - (interval '1 day' * v_age_days)
        and (
          exists (
            select 1
            from jsonb_array_elements_text(coalesce(c.tags, '[]'::jsonb)) t(tag)
            where lower(btrim(t.tag)) = lower(btrim(p_property_class))
          )
          or lower(coalesce(c.details->>'property_type', '')) = lower(btrim(p_property_class))
          or lower(coalesce(c.details->>'Tipo de Propiedad', '')) = lower(btrim(p_property_class))
        )
    ),
    parsed as (
      select
        b.comp_id,
        b.price,
        b.area_m2,
        ST_SetSRID(ST_MakePoint(b.lon, b.lat), 4326)::geography as comp_geom
      from base b
      where b.lat is not null
        and b.lon is not null
        and b.area_m2 is not null
        and b.area_m2 > 0
        and b.area_m2 between p_area_m2 * 0.60 and p_area_m2 * 1.80
    )
    select count(*)::int
    into v_count
    from parsed p
    where ST_DWithin(p.comp_geom, v_geom, v_radius);

    if v_count >= v_min_comps then
      exit;
    end if;
  end loop;

  if v_count < v_min_comps then
    v_radius := null;
  end if;

  return query
  with base as (
    select
      c.external_id::text as comp_id,
      c.title,
      c.source,
      c.url,
      c.listing_type,
      coalesce(
        nullif((select t from jsonb_array_elements_text(coalesce(c.tags, '[]'::jsonb)) t limit 1), ''),
        nullif(c.details->>'property_type', ''),
        nullif(c.details->>'Tipo de Propiedad', '')
      ) as comp_class,
      c.price::numeric as price,
      nullif(regexp_replace(replace(coalesce(c.specs->>'area_m2', ''), ',', ''), '[^0-9\.\-]', '', 'g'), '')::numeric as area_m2,
      nullif(regexp_replace(replace(coalesce(c.specs->>'bedrooms', ''), ',', ''), '[^0-9\.\-]', '', 'g'), '')::numeric::int as beds,
      nullif(regexp_replace(replace(coalesce(c.specs->>'bathrooms', ''), ',', ''), '[^0-9\.\-]', '', 'g'), '')::numeric as baths,
      nullif(regexp_replace(replace(coalesce(c.specs->>'parking', ''), ',', ''), '[^0-9\.\-]', '', 'g'), '')::numeric::int as parking,
      nullif(c.location->>'latitude', '')::double precision as lat,
      nullif(c.location->>'longitude', '')::double precision as lon,
      coalesce(c.active, false) as is_active,
      greatest(0::numeric, extract(epoch from (v_now - coalesce(c.last_updated, c.published_date::timestamptz))) / 86400.0) as days_old
    from public.scrapped_data c
    where c.price is not null
      and c.price > 0
      and c.listing_type = p_listing_type
      and coalesce(c.last_updated, c.published_date::timestamptz) >= v_now - (interval '1 day' * v_age_days)
      and (
        exists (
          select 1
          from jsonb_array_elements_text(coalesce(c.tags, '[]'::jsonb)) t(tag)
          where lower(btrim(t.tag)) = lower(btrim(p_property_class))
        )
        or lower(coalesce(c.details->>'property_type', '')) = lower(btrim(p_property_class))
        or lower(coalesce(c.details->>'Tipo de Propiedad', '')) = lower(btrim(p_property_class))
      )
  ),
  parsed as (
    select
      b.*,
      ST_SetSRID(ST_MakePoint(b.lon, b.lat), 4326)::geography as comp_geom
    from base b
    where b.lat is not null
      and b.lon is not null
      and b.area_m2 is not null
      and b.area_m2 > 0
      and b.area_m2 between p_area_m2 * 0.60 and p_area_m2 * 1.80
  ),
  scoped as (
    select p.*
    from parsed p
    where v_radius is null
       or ST_DWithin(p.comp_geom, v_geom, v_radius)
  ),
  enriched as (
    select
      s.*,
      ST_Distance(s.comp_geom, v_geom) as dist_m,
      (s.price / s.area_m2) as ppm2,

      case
        when v_radius is null then exp(-ST_Distance(s.comp_geom, v_geom) / 8000.0)
        else exp(-ST_Distance(s.comp_geom, v_geom) / greatest(v_radius::numeric / 2.0, 1.0))
      end::numeric as w_dist,

      exp(-s.days_old / 60.0)::numeric as w_time,

      case
        when s.is_active then 1.00::numeric
        when s.days_old <= 90 then 0.70::numeric
        else 0.45::numeric
      end as w_status,

      exp(-abs(ln(s.area_m2 / p_area_m2)) / 0.35)::numeric as w_size,

      (
        case
          when p_bedrooms is null then 1.00
          when s.beds is null then 0.95
          else exp(-abs(s.beds - p_bedrooms)::numeric / 1.5)
        end
        *
        case
          when p_bathrooms is null then 1.00
          when s.baths is null then 0.95
          else exp(-abs(s.baths - p_bathrooms) / 1.0)
        end
        *
        case
          when p_parking is null then 1.00
          when s.parking is null then 0.95
          else exp(-abs(s.parking - p_parking)::numeric / 1.0)
        end
      )::numeric as w_feat
    from scoped s
  ),
  scored as materialized (
    select
      e.*,
      (e.w_dist * e.w_time * e.w_status * e.w_size * e.w_feat)::numeric as w_total
    from enriched e
  ),
  iqr as materialized (
    select
      percentile_cont(0.25) within group (order by sc.ppm2) as q1,
      percentile_cont(0.75) within group (order by sc.ppm2) as q3
    from scored sc
  ),
  trimmed as (
    select sc.*
    from scored sc
    cross join iqr q
    where q.q1 is null
       or q.q3 is null
       or sc.ppm2 between (q.q1 - 1.5 * (q.q3 - q.q1))
                      and (q.q3 + 1.5 * (q.q3 - q.q1))
  ),
  ranked as (
    select
      row_number() over (order by t.w_total desc, t.dist_m asc, t.days_old asc) as rk,
      t.*
    from trimmed t
  )
  select
    case when v_radius is null then 'national_fallback' else 'local' end as match_mode,
    v_radius as selected_radius_m,
    r.rk::int as comp_rank,
    r.comp_id as comp_external_id,
    r.title as comp_title,
    r.source as comp_source,
    r.listing_type as comp_listing_type,
    r.comp_class as comp_property_class,
    round(r.price, 2) as comp_price,
    round(r.area_m2, 2) as comp_area_m2,
    round(r.ppm2, 2) as comp_price_m2,
    round(r.dist_m)::int as distance_m,
    round(r.days_old)::int as days_old,
    r.is_active as comp_active,
    r.beds as comp_bedrooms,
    r.baths as comp_bathrooms,
    r.parking as comp_parking,
    round(r.w_dist, 6) as distance_weight,
    round(r.w_time, 6) as freshness_weight,
    round(r.w_status, 6) as status_weight,
    round(r.w_size, 6) as size_weight,
    round(r.w_feat, 6) as feature_weight,
    round(r.w_total, 6) as total_weight,
    case
      when v_subject_ppm2 is null then null
      else round(((r.ppm2 - v_subject_ppm2) / nullif(v_subject_ppm2, 0)) * 100.0, 2)
    end as delta_vs_subject_ppm2_pct,
    r.url as comp_url
  from ranked r
  where r.rk <= v_limit
  order by r.rk;

end;
$$;

grant execute on function public.avm_nearest_matches(
  double precision, double precision, numeric, text, text, integer, numeric, integer, numeric, integer, integer, integer, integer[]
) to anon, authenticated;

-- =========================================================
-- 2) Point valuation summary using nearest matches
-- =========================================================
create or replace function public.avm_value_point(
  p_lat double precision,
  p_lon double precision,
  p_area_m2 numeric,
  p_listing_type text,
  p_property_class text,
  p_bedrooms integer default null,
  p_bathrooms numeric default null,
  p_parking integer default null,
  p_min_comps integer default 8,
  p_max_age_days integer default 180,
  p_radius_ladder_m integer[] default array[1000, 2000, 3000, 5000, 8000, 12000, 20000]
)
returns table(
  listing_type text,
  property_class text,
  area_m2 numeric,
  radius_used_m integer,
  comps_used integer,
  est_price numeric,
  est_low numeric,
  est_high numeric,
  est_price_m2 numeric,
  confidence numeric,
  method text,
  notes text
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_cnt int;
  v_radius int;
  v_mode text;
  v_wppm2 numeric;
  v_p25 numeric;
  v_p75 numeric;
  v_disp numeric;
  v_conf numeric;
begin
  if p_lat is null or p_lon is null then
    raise exception using errcode = '22023', message = 'latitude and longitude are required';
  end if;

  if p_area_m2 is null or p_area_m2 <= 0 then
    raise exception using errcode = '22023', message = 'area_m2 is required and must be > 0';
  end if;

  if p_listing_type is null or btrim(p_listing_type) = '' then
    raise exception using errcode = '22023', message = 'listing_type is required';
  end if;

  if p_property_class is null or btrim(p_property_class) = '' then
    raise exception using errcode = '22023', message = 'property_class is required';
  end if;

  with comps as materialized (
    select *
    from public.avm_nearest_matches(
      p_lat => p_lat,
      p_lon => p_lon,
      p_area_m2 => p_area_m2,
      p_listing_type => p_listing_type,
      p_property_class => p_property_class,
      p_bedrooms => p_bedrooms,
      p_bathrooms => p_bathrooms,
      p_parking => p_parking,
      p_subject_price => null::numeric,
      p_min_comps => coalesce(p_min_comps, 8),
      p_limit => greatest(coalesce(p_min_comps, 8) * 4, 30),
      p_max_age_days => coalesce(p_max_age_days, 180),
      p_radius_ladder_m => coalesce(p_radius_ladder_m, array[1000, 2000, 3000, 5000, 8000, 12000, 20000])
    )
  ),
  agg as (
    select
      count(*)::int as cnt,
      max(selected_radius_m) as radius_used,
      min(match_mode) as mode_used,
      case
        when nullif(sum(total_weight), 0) is null then null
        else sum(total_weight * comp_price_m2) / nullif(sum(total_weight), 0)
      end as wppm2,
      percentile_cont(0.25) within group (order by comp_price_m2) as p25,
      percentile_cont(0.75) within group (order by comp_price_m2) as p75
    from comps
  )
  select
    a.cnt,
    a.radius_used,
    a.mode_used,
    a.wppm2,
    a.p25,
    a.p75,
    coalesce((a.p75 - a.p25) / nullif(a.wppm2, 0), 0)
  into
    v_cnt, v_radius, v_mode, v_wppm2, v_p25, v_p75, v_disp
  from agg a;

  if coalesce(v_cnt, 0) < greatest(4, coalesce(p_min_comps, 8) / 2) or v_wppm2 is null then
    return query
    select
      p_listing_type,
      p_property_class,
      p_area_m2,
      v_radius,
      coalesce(v_cnt, 0),
      null::numeric,
      null::numeric,
      null::numeric,
      null::numeric,
      0::numeric,
      'insufficient_data'::text,
      'not enough comparable listings after filters'::text;
    return;
  end if;

  v_conf := greatest(
    0.03,
    least(
      0.95,
      least(1.0, v_cnt::numeric / 15.0) * exp(-coalesce(v_disp, 0))
    )
  );

  return query
  select
    p_listing_type,
    p_property_class,
    p_area_m2,
    v_radius,
    v_cnt,
    round(p_area_m2 * v_wppm2, 2) as est_price,
    round(p_area_m2 * coalesce(v_p25, v_wppm2), 2) as est_low,
    round(p_area_m2 * coalesce(v_p75, v_wppm2), 2) as est_high,
    round(v_wppm2, 2) as est_price_m2,
    round(v_conf, 3) as confidence,
    case when coalesce(v_mode, 'local') = 'local' then 'radius_weighted_ppm2' else 'national_fallback' end as method,
    case when coalesce(v_mode, 'local') = 'local'
         then 'valuation based on nearest comparable listings'
         else 'insufficient local comps, used broader fallback comps'
    end as notes;
end;
$$;

grant execute on function public.avm_value_point(
  double precision, double precision, numeric, text, text, integer, numeric, integer, integer, integer, integer[]
) to anon, authenticated;

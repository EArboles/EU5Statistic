from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_materialized_view import PGMaterializedView

# --- Functions ---

get_available_years = PGFunction(
    schema="public",
    signature="get_available_years(p_start_year integer, p_end_year integer)",
    definition="""
RETURNS TABLE(year integer)
 LANGUAGE sql
 STABLE
AS $function$
    SELECT DISTINCT year
    FROM public.country_population_statistics
    WHERE year BETWEEN p_start_year AND p_end_year
    ORDER BY year;
$function$
""",
)

get_religion_statistics = PGFunction(
    schema="public",
    signature="get_religion_statistics(p_start_year integer, p_end_year integer)",
    definition="""
RETURNS TABLE(religion_name character varying, year integer, population bigint)
 LANGUAGE sql
 STABLE
AS $function$
    WITH 
    available_years AS (
         SELECT * FROM get_available_years(p_start_year, p_end_year)
    ),
    available_religions AS (
        SELECT DISTINCT r.id, r.localization_name
        FROM public.religions r
        JOIN public.country_population_statistics cps ON cps.religion_id = r.id
        WHERE cps.year BETWEEN p_start_year AND p_end_year
    ),
    actual_data AS (
        SELECT 
            religion_id,
            year,
            SUM(population_size) AS total_pop
        FROM public.country_population_statistics
        WHERE year BETWEEN p_start_year AND p_end_year
        GROUP BY religion_id, year
    ),
    all_combinations AS (
        SELECT
            ar.id AS religion_id,
            ar.localization_name AS religion_name,
            ay.year,
            COALESCE(ad.total_pop, 0) AS population
        FROM available_religions ar
        CROSS JOIN available_years ay
        LEFT JOIN actual_data ad ON ad.religion_id = ar.id AND ad.year = ay.year
    )
    SELECT 
        religion_name,
        year,
        population
    FROM all_combinations
    ORDER BY religion_name, year;
$function$
""",
)

get_culture_statistics = PGFunction(
    schema="public",
    signature="get_culture_statistics(p_start_year integer, p_end_year integer)",
    definition="""
 RETURNS TABLE(culture_name character varying, year integer, population bigint)
 LANGUAGE sql
 STABLE
AS $function$
    WITH 
    available_years AS (
         SELECT * FROM get_available_years(p_start_year, p_end_year)
    ),
    available_cultures AS (
        SELECT DISTINCT c.id, c.localization_name
        FROM public.cultures c
        JOIN public.country_population_statistics cps ON cps.culture_id = c.id
        WHERE cps.year BETWEEN p_start_year AND p_end_year
    ),
    actual_data AS (
        SELECT 
            culture_id,
            year,
            SUM(population_size) AS total_pop
        FROM public.country_population_statistics
        WHERE year BETWEEN p_start_year AND p_end_year
        GROUP BY culture_id, year
    ),
    all_combinations AS (
        SELECT
            ac.id AS culture_id,
            ac.localization_name AS culture_name,
            ay.year,
            COALESCE(ad.total_pop, 0) AS population
        FROM available_cultures ac
        CROSS JOIN available_years ay
        LEFT JOIN actual_data ad ON ad.culture_id = ac.id AND ad.year = ay.year
    )
    SELECT 
        culture_name,
        year,
        population
    FROM all_combinations
    ORDER BY culture_name, year;
$function$
""",
)

get_country_summary = PGFunction(
    schema="public",
    signature="get_country_summary(p_start_year integer, p_end_year integer)",
    definition="""
RETURNS TABLE(country_name character varying, year integer, total_population bigint, primary_culture_percent numeric, primary_religion_percent numeric, num_locations integer)
 LANGUAGE sql
 STABLE
AS $function$
    WITH 
    available_years AS (
        SELECT * FROM get_available_years(p_start_year, p_end_year)
    ),
    -- Only countries that have entries in `country_statistics` within the specified range
    countries_in_range AS (
        SELECT DISTINCT c.id, c.localization_name
        FROM public.countries c
        JOIN public.country_statistics cs ON cs.country_id = c.id
        WHERE cs.year BETWEEN p_start_year AND p_end_year
    ),
    -- Total population by country and year
    total_pop AS (
        SELECT 
            country_id,
            year,
            SUM(population_size) AS total_pop
        FROM public.country_population_statistics
        WHERE year BETWEEN p_start_year AND p_end_year
        GROUP BY country_id, year
    ),
    -- Population of the primary culture
    culture_pop AS (
        SELECT 
            cps.country_id,
            cps.year,
            SUM(cps.population_size) AS cult_pop
        FROM public.country_population_statistics cps
        JOIN public.country_statistics cs 
            ON cs.country_id = cps.country_id AND cs.year = cps.year
        WHERE cps.year BETWEEN p_start_year AND p_end_year
          AND cps.culture_id = cs.primary_culture_id
        GROUP BY cps.country_id, cps.year
    ),
    -- Population of the primary religion
    religion_pop AS (
        SELECT 
            cps.country_id,
            cps.year,
            SUM(cps.population_size) AS rel_pop
        FROM public.country_population_statistics cps
        JOIN public.country_statistics cs 
            ON cs.country_id = cps.country_id AND cs.year = cps.year
        WHERE cps.year BETWEEN p_start_year AND p_end_year
          AND cps.religion_id = cs.primary_religion_id
        GROUP BY cps.country_id, cps.year
    ),
    -- Combining all data
    combined AS (
        SELECT 
            c.id AS country_id,
            c.localization_name AS country_name,
            ay.year,
            COALESCE(tp.total_pop, 0) AS total_population,
            cp.cult_pop,
            rp.rel_pop,
            COALESCE(cs.num_locations, 0) AS num_locations
        FROM countries_in_range c
        CROSS JOIN available_years ay
        LEFT JOIN total_pop tp ON tp.country_id = c.id AND tp.year = ay.year
        LEFT JOIN culture_pop cp ON cp.country_id = c.id AND cp.year = ay.year
        LEFT JOIN religion_pop rp ON rp.country_id = c.id AND rp.year = ay.year
        LEFT JOIN public.country_statistics cs ON cs.country_id = c.id AND cs.year = ay.year
    )
    SELECT 
        country_name,
        year,
        total_population,
        CASE 
            WHEN total_population > 0 AND cult_pop IS NOT NULL 
            THEN ROUND((cult_pop::NUMERIC / total_population) * 100, 2) 
            ELSE NULL 
        END AS primary_culture_percent,
        CASE 
            WHEN total_population > 0 AND rel_pop IS NOT NULL 
            THEN ROUND((rel_pop::NUMERIC / total_population) * 100, 2) 
            ELSE NULL 
        END AS primary_religion_percent,
        num_locations
    FROM combined
    ORDER BY country_name, year;
$function$
""",
)

get_all_vassals = PGFunction(
    schema="public",
    signature="get_all_vassals(p_country_tag character varying, p_year integer)",
    definition="""
returns TABLE(vassal_id integer)
 LANGUAGE sql
 STABLE
AS $function$
    WITH RECURSIVE vassals_tree AS (
        -- Initial level – direct vassals
        SELECT v.vassal_id
        FROM public.vassalage v
        JOIN public.countries c ON c.id = v.suzerain_id
        WHERE c.tag = p_country_tag AND v.year = p_year
        
        UNION ALL
        
        -- Recursively find the vassals of vassals
        SELECT v.vassal_id
        FROM public.vassalage v
        JOIN vassals_tree vt ON vt.vassal_id = v.suzerain_id
        WHERE v.year = p_year
    )
    SELECT vassal_id FROM vassals_tree;
$function$
""",
)

get_target_country_cultures = PGFunction(
    schema="public",
    signature="get_target_country_cultures(p_tag character varying, p_start_year integer, p_end_year integer)",
    definition="""
 RETURNS TABLE(culture_name character varying, year integer, pop_in_country bigint, pop_in_vassals bigint, world_pop bigint)
 LANGUAGE plpgsql
 STABLE
AS $function$
BEGIN
    RETURN QUERY
    WITH 
    target_country AS (
        SELECT id FROM public.countries WHERE tag = p_tag
    ),
    available_years AS (
        SELECT * FROM get_available_years(p_start_year, p_end_year)
    ),
    relevant_cultures AS (
        SELECT DISTINCT c.id, c.localization_name
        FROM public.cultures c
        WHERE EXISTS (
            SELECT 1 FROM public.country_population_statistics cps
            JOIN target_country tc ON cps.country_id = tc.id
            WHERE cps.culture_id = c.id 
              AND cps.year BETWEEN p_start_year AND p_end_year
        )
        OR EXISTS (
            SELECT 1 FROM public.country_population_statistics cps
            JOIN LATERAL get_all_vassals(p_tag, cps.year) vt ON vt.vassal_id = cps.country_id
            WHERE cps.culture_id = c.id 
              AND cps.year BETWEEN p_start_year AND p_end_year
        )
    ),
    country_culture_pop AS (
        SELECT 
            cps.culture_id,
            cps.year AS c_year,
            SUM(cps.population_size)::BIGINT AS pop
        FROM public.country_population_statistics cps
        JOIN target_country tc ON cps.country_id = tc.id
        WHERE cps.year BETWEEN p_start_year AND p_end_year
        GROUP BY cps.culture_id, cps.year
    ),
    vassal_culture_pop AS (
        SELECT 
            cps.culture_id,
            cps.year AS v_year,
            SUM(cps.population_size)::BIGINT AS pop
        FROM public.country_population_statistics cps
        JOIN LATERAL get_all_vassals(p_tag, cps.year) vt ON vt.vassal_id = cps.country_id
        WHERE cps.year BETWEEN p_start_year AND p_end_year
        GROUP BY cps.culture_id, cps.year
    ),
    world_culture_pop AS (
        SELECT 
            culture_id,
            cps.year AS w_year,
            SUM(population_size)::BIGINT AS pop
        FROM public.country_population_statistics cps
        WHERE cps.year BETWEEN p_start_year AND p_end_year
        GROUP BY culture_id, cps.year
    ),
    all_combinations AS (
        SELECT 
            rc.id AS culture_id,
            rc.localization_name AS culture_name,
            ay.year,
            COALESCE(ccp.pop, 0) AS pop_country,
            COALESCE(vcp.pop, 0) AS pop_vassals,
            COALESCE(wcp.pop, 0) AS pop_world
        FROM relevant_cultures rc
        CROSS JOIN available_years ay
        LEFT JOIN country_culture_pop ccp ON ccp.culture_id = rc.id AND ccp.c_year = ay.year
        LEFT JOIN vassal_culture_pop vcp ON vcp.culture_id = rc.id AND vcp.v_year = ay.year
        LEFT JOIN world_culture_pop wcp ON wcp.culture_id = rc.id AND wcp.w_year = ay.year
    )
    SELECT 
        alc.culture_name,
        alc.year,
        pop_country,
        pop_vassals,
        pop_world
    FROM all_combinations alc
    ORDER BY culture_name, year;
END;
$function$
""",
)

get_target_country_religions = PGFunction(
    schema="public",
    signature="get_target_country_religions(p_tag character varying, p_start_year integer, p_end_year integer)",
    definition="""
RETURNS TABLE(religion_name character varying, year integer, pop_in_country bigint, pop_in_vassals bigint, world_pop bigint)
 LANGUAGE plpgsql
 STABLE
AS $function$
BEGIN
    RETURN QUERY
    WITH 
    target_country AS (
        SELECT id FROM public.countries WHERE tag = p_tag
    ),
    available_years AS (
        SELECT * FROM get_available_years(p_start_year, p_end_year)
    ),
    relevant_religions AS (
        SELECT DISTINCT r.id, r.localization_name
        FROM public.religions r
        WHERE EXISTS (
            SELECT 1 FROM public.country_population_statistics cps
            JOIN target_country tc ON cps.country_id = tc.id
            WHERE cps.religion_id = r.id 
              AND cps.year BETWEEN p_start_year AND p_end_year
        )
        OR EXISTS (
            SELECT 1 FROM public.country_population_statistics cps
            JOIN LATERAL get_all_vassals(p_tag, cps.year) vt ON vt.vassal_id = cps.country_id
            WHERE cps.religion_id = r.id 
              AND cps.year BETWEEN p_start_year AND p_end_year
        )
    ),
    country_religion_pop AS (
        SELECT 
            cps.religion_id,
            cps.year AS c_year,
            SUM(cps.population_size)::BIGINT AS pop
        FROM public.country_population_statistics cps
        JOIN target_country tc ON cps.country_id = tc.id
        WHERE cps.year BETWEEN p_start_year AND p_end_year
        GROUP BY cps.religion_id, cps.year
    ),
    vassal_religion_pop AS (
        SELECT 
            cps.religion_id,
            cps.year AS v_year,
            SUM(cps.population_size)::BIGINT AS pop
        FROM public.country_population_statistics cps
        JOIN LATERAL get_all_vassals(p_tag, cps.year) vt ON vt.vassal_id = cps.country_id
        WHERE cps.year BETWEEN p_start_year AND p_end_year
        GROUP BY cps.religion_id, cps.year
    ),
    world_religion_pop AS (
        SELECT 
            religion_id,
            cps.year AS w_year,
            SUM(population_size)::BIGINT AS pop
        FROM public.country_population_statistics cps
        WHERE cps.year BETWEEN p_start_year AND p_end_year
        GROUP BY religion_id, cps.year
    ),
    all_combinations AS (
        SELECT 
            rr.id AS religion_id,
            rr.localization_name AS religion_name,
            ay.year,
            COALESCE(crp.pop, 0) AS pop_country,
            COALESCE(vrp.pop, 0) AS pop_vassals,
            COALESCE(wrp.pop, 0) AS pop_world
        FROM relevant_religions rr
        CROSS JOIN available_years ay
        LEFT JOIN country_religion_pop crp ON crp.religion_id = rr.id AND crp.c_year = ay.year
        LEFT JOIN vassal_religion_pop vrp ON vrp.religion_id = rr.id AND vrp.v_year = ay.year
        LEFT JOIN world_religion_pop wrp ON wrp.religion_id = rr.id AND wrp.w_year = ay.year
    )
    SELECT 
        alc.religion_name,
        alc.year,
        pop_country,
        pop_vassals,
        pop_world
    FROM all_combinations alc
    ORDER BY religion_name, year;
END;
$function$
""",
)


get_world_location_stats = PGFunction(
    schema="public",
    signature="get_world_location_stats(p_start_year integer, p_end_year integer)",
    definition="""
RETURNS TABLE(location_name character varying, year integer, total_population bigint, avg_literacy numeric)
 LANGUAGE sql
 STABLE
AS $function$
    SELECT 
        location_name, year, total_population, avg_literacy
    FROM location_stats_view
    WHERE year BETWEEN p_start_year AND p_end_year
    ORDER BY location_name, year;
$function$
""",
)

get_country_location_stats = PGFunction(
    schema="public",
    signature="get_country_location_stats(p_tag character varying, p_start_year integer, p_end_year integer)",
    definition="""
RETURNS TABLE(location_name character varying, year integer, total_population bigint, avg_literacy numeric, estate_burghers numeric, estate_soldiers numeric, estate_nobles numeric, estate_peasants numeric, estate_slaves numeric, estate_clergy numeric, estate_tribesmen numeric, estate_laborers numeric)
 LANGUAGE plpgsql
 STABLE
AS $function$
BEGIN
    RETURN QUERY
    WITH 
    target_country AS (
        SELECT id FROM public.countries WHERE tag = p_tag
    ),
    -- All pairs (location, year) where the country held the location within the specified range
    ownership AS (
        SELECT ls.location_id, ls.year
        FROM public.location_statistics ls
        JOIN target_country tc ON ls.country_id = tc.id
        WHERE ls.year BETWEEN p_start_year AND p_end_year
    ),
    -- Baseline data (population, literacy) from the presentation – for ownership pairs only
    base_data AS (
        SELECT 
            o.location_id,
            l.localization_name,
            o.year,
            COALESCE(vs.total_population, 0)::BIGINT AS total_population,
            vs.avg_literacy
        FROM ownership o
        JOIN public.locations l ON l.id = o.location_id
        LEFT JOIN location_stats_view vs ON vs.location_id = o.location_id AND vs.year = o.year
    ),
    -- Aggregation of the population by estate – for ownership pairs only
    estate_agg AS (
        SELECT 
            lps.location_id,
            lps.year,
            SUM(CASE WHEN lps.estate_id = 1 THEN lps.population_size ELSE 0 END) AS e1_pop,
            SUM(CASE WHEN lps.estate_id = 2 THEN lps.population_size ELSE 0 END) AS e2_pop,
            SUM(CASE WHEN lps.estate_id = 3 THEN lps.population_size ELSE 0 END) AS e3_pop,
            SUM(CASE WHEN lps.estate_id = 4 THEN lps.population_size ELSE 0 END) AS e4_pop,
            SUM(CASE WHEN lps.estate_id = 5 THEN lps.population_size ELSE 0 END) AS e5_pop,
            SUM(CASE WHEN lps.estate_id = 6 THEN lps.population_size ELSE 0 END) AS e6_pop,
            SUM(CASE WHEN lps.estate_id = 7 THEN lps.population_size ELSE 0 END) AS e7_pop,
            SUM(CASE WHEN lps.estate_id = 8 THEN lps.population_size ELSE 0 END) AS e8_pop
        FROM public.location_population_statistics lps
        JOIN ownership o ON o.location_id = lps.location_id AND o.year = lps.year
        GROUP BY lps.location_id, lps.year
    )
    SELECT 
        bd.localization_name,
        bd.year,
        bd.total_population,
        bd.avg_literacy,
        ROUND(CASE WHEN bd.total_population > 0 THEN (ea.e1_pop::NUMERIC / bd.total_population) * 100 ELSE 0 END, 2),
        ROUND(CASE WHEN bd.total_population > 0 THEN (ea.e2_pop::NUMERIC / bd.total_population) * 100 ELSE 0 END, 2),
        ROUND(CASE WHEN bd.total_population > 0 THEN (ea.e3_pop::NUMERIC / bd.total_population) * 100 ELSE 0 END, 2),
        ROUND(CASE WHEN bd.total_population > 0 THEN (ea.e4_pop::NUMERIC / bd.total_population) * 100 ELSE 0 END, 2),
        ROUND(CASE WHEN bd.total_population > 0 THEN (ea.e5_pop::NUMERIC / bd.total_population) * 100 ELSE 0 END, 2),
        ROUND(CASE WHEN bd.total_population > 0 THEN (ea.e6_pop::NUMERIC / bd.total_population) * 100 ELSE 0 END, 2),
        ROUND(CASE WHEN bd.total_population > 0 THEN (ea.e7_pop::NUMERIC / bd.total_population) * 100 ELSE 0 END, 2),
        ROUND(CASE WHEN bd.total_population > 0 THEN (ea.e8_pop::NUMERIC / bd.total_population) * 100 ELSE 0 END, 2)
    FROM base_data bd
    LEFT JOIN estate_agg ea ON ea.location_id = bd.location_id AND ea.year = bd.year
    ORDER BY bd.year, bd.localization_name;
END;
$function$
""",
)

# --- Materialized View ---

# ATTENTION: Indexes on this view are managed separately.
# See the migration named "*add_index_on_location_stats_view*".
# alembic_utils does not support indexes for materialized views.
location_stats_view = PGMaterializedView(
    schema="public",
    signature="location_stats_view",
    definition="""
 SELECT lps.location_id,
    l.localization_name AS location_name,
    lps.year,
    sum(lps.population_size) AS total_population,
    COALESCE(
        ROUND(
            (SUM(lps.population_size * lps.literacy)::numeric / NULLIF(SUM(lps.population_size), 0)) * 100, 
            2
        ), 
        0
    ) AS avg_literacy
   FROM location_population_statistics lps
     JOIN locations l ON l.id = lps.location_id
  GROUP BY lps.location_id, l.localization_name, lps.year;
  """,
    with_data=True,
)

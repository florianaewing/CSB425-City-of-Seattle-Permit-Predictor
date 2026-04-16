# Seattle Permit Predictor — EDA Phase 1 Report
*Dataset Understanding, Transformations & Open Questions*
*April 2026 | Prepared for internal review prior to modeling*

---

## What We're Working With

Three datasets were sourced from the Seattle Open Data portal, filtered to permits applied on or after January 1, 2020. The **Building Permits** dataset (`df_permits`) contains 40,183 rows at one row per permit, and serves as the backbone of the entire analysis. It carries the primary outcome variable — `totaldaysplanreview` — alongside permit classification, project cost, address, zoning, housing type, and a set of aggregated timeline fields. The **Plan Review** dataset (`df_review`) contains 196,041 rows at multiple rows per permit, one per reviewer per review cycle, and was expected to provide cycle-level detail for enriching the permit backbone. The **Plan Comments** dataset (`df_comments`) contains 26,299 rows at one row per written correction comment, and was evaluated as a potential source of NLP signal.

Early in the investigation we discovered that only 15,066 of 40,183 permits (37.5%) have any corresponding rows in `df_review`. We initially suspected a data coverage gap, but clarification from the city liaison revealed the structural reason: `df_review` captures the correction cycle records generated when a plan is sent back for revisions. Permits that proceeded through review without generating exported cycle records — whether due to approval pathway, archiving behavior, or export limitations — simply do not appear in the review dataset. This means review records are enrichment data where available, not a reliable indicator of process path, and `df_permits` must stand alone as the modeling backbone.

The comments dataset told a similar story. Only 707 unique permits have any comment records, 97.6% of which also have review records. Comments skew heavily toward Single Family/Duplex permits (89.8%) and toward permits with above-average review times (median 156 days vs 89 days for permits without comments). With 1.7% coverage and strong selection bias, the comments dataset cannot support NLP modeling and will be retained only as a qualitative reference.

---

## What We Learned About the Target Variable

The primary outcome variable, `totaldaysplanreview`, measures the total elapsed days from plan submission to review completion. Of the 40,183 permits in the post-2020 population, 17,371 (43.2%) have no value for this field. Investigation of those nulls revealed two distinct causes. The first is legitimate: permits still in active statuses such as Reviews In Process, Awaiting Information, or Corrections Required have no completed review time yet and are correctly null. The second is a genuine data quality gap: 9,060 permits with a status of Completed are missing `totaldaysplanreview` entirely. These completed-but-null permits are systematically different from completed permits that do have values — they skew heavily toward Single Family/Duplex (80% vs 58%), are almost exclusively Addition/Alteration type (89% vs 61%), and have dramatically lower project costs (median $40k vs $180k). These are likely small residential jobs that went through an expedited or streamlined review pathway that does not generate a recorded review time in the source system. This represents a known structural bias: the final modeling population will underrepresent simple, low-cost residential alteration permits, and the web tool should surface a caveat for users in that category.

Among the 22,812 permits with non-null `totaldaysplanreview`, we found 80 negative values and 130 zero values, both of which are impossible and likely the result of date entry errors in the source system. An additional 179 permits exceeded 1,095 days (three years), which were treated as extraordinary cases — permits likely paused, disputed, or subject to exceptional circumstances — and excluded from the modeling population. The raw distribution is heavily right-skewed (skewness 3.446, kurtosis 17.319), with a median of 91 days and a mean of 153 days. Log transformation reduced skewness to -0.368, confirming that `log(1 + totaldaysplanreview)` is the appropriate modeling target.

Median review time showed a meaningful temporal trend: it rose from 97 days in 2020 to a peak of 116 days in 2022, then declined steadily to 76 days in 2025. This likely reflects a combination of COVID-era processing delays and subsequent process improvements. Permits applied in 2026 were dropped from the modeling population entirely, as their review clocks are almost certainly still running and their recorded values (median 30 days) are not comparable to completed reviews.

---

## Feature Landscape

After schema audit, null analysis, and signal testing, the following features are confirmed as legitimate model inputs — meaning they are all available at the time of permit submission and do not leak any post-submission process information.

`permittypedesc` is the single strongest categorical predictor, with a median review time spread from 16 days (Tenant Improvement) to 211 days (New construction) — a 13x range across 8 categories. `dwellingunittype` carries exceptional signal as well, ranging from 61 days median for Commercial to 270 days for Townhouse. `housingcategory` differentiates Middle Housing (172 days) from Pre-Approved DADU Plans (58 days) and is directly relevant to the tool's use case for applicants comparing project options. `permitclass` separates Multifamily (153 days) from Commercial (51 days) with a clear gradient. Zoning, while too high-cardinality at 676 unique values to use directly, was reduced to zone family prefixes (NR, SF, LR, NC, etc.) and retains meaningful signal — LR-family zones show median review times around 190 days while NR3 sits at 88 days.

Among numeric features, `estprojectcost` and `housingunitsadded` both show weak raw correlations with the target (r=0.056 and r=0.137 respectively) but substantially stronger log-scale correlations (r=0.200 and r=0.403), confirming nonlinear relationships that will be better captured by tree-based models or with explicit log transformation. Latitude and longitude are included as spatial proxies for neighborhood-level effects, though their direct correlation with the target is near zero — their value will likely emerge through interaction effects rather than as standalone predictors.

Several fields that appear predictive were deliberately excluded from the model feature set because they are process outcome variables not available at submission time: `daysplanreviewcity` (r=0.694 with target), `daysinitialplanreview` (r=0.484), `daysoutcorrections`, `numberreviewcycles`, and `daysissuepermitcity`. These will be retained in the dataset for post-hoc analysis and for the Permit Risk Score framework, but must not enter the predictive model.

---

## Transformations Applied

All transformations were applied to the modeling population only. The raw datasets (`raw_permits`, `raw_review`, `raw_comments`) remain untouched in memory throughout.

The post-2020 filter was applied first, using `applieddate` as the filter field for both `df_permits` and `df_review`, and `documentdate` as a proxy for `df_comments`. Dead-weight columns were then removed across all three datasets — specifically URL strings, redundant geographic fields, columns with over 88% nulls, and permit-level fields duplicated across the review and permits datasets. All date columns were cast to `datetime64` and all numeric fields were explicitly coerced with error handling.

The modeling population (`df_model`) was defined by the following sequential exclusion criteria applied to `df_permits`: remove permits with null `totaldaysplanreview` (17,371), remove permits with negative or zero review time (210), remove permits with review time exceeding 1,095 days (179), and remove 2026 permits with incomplete review cycles (374). This produced a final modeling population of 22,049 permits.

Within `df_model`, data errors were corrected: 1,136 negative `housingunits` values and 1 negative `daysissuepermitcity` value were set to null; 447 zero `estprojectcost` values were set to null; and 220 extreme `daysoutcorrections` values above the 99th percentile (1,005 days) were capped. Zoning was reduced from 676 unique values to 21 zone family prefixes plus an Unknown category. Null values in `housingcategory` (6,878), `dwellingunittype` (3,297), and `permittypedesc` (515) were filled with an explicit 'Unknown' category rather than dropping rows, on the basis that missingness may itself carry signal. Log transforms were applied to `estprojectcost`, `housingunitsadded`, and the target variable.

The final clean modeling population contains 22,049 rows with zero nulls across all categorical features, 2.0% nulls on `log_estprojectcost`, 11.1% nulls on `log_housingunitsadded`, and 0.1% nulls on latitude/longitude.

---

## Open Questions for the City Liaison

**On negative and very short review times.** The dataset contains 80 permits with negative `totaldaysplanreview` values and 130 with zero days, as well as 455 additional permits with review times under 7 days. These values are either data entry errors or reflect a review pathway we don't understand. Can the city explain how a permit could record a negative or zero review time? Are these corrections applied retroactively, date entry mistakes, or permits that bypassed normal review for a specific reason?

**On the 9,060 completed permits missing review time.** These are fully completed permits — the process is over — but they have no recorded `totaldaysplanreview`. They skew strongly toward small residential addition/alteration projects. Is there a specific review pathway (over-the-counter, express review, pre-approved plan sets) that does not generate a `totaldaysplanreview` entry in the system? Understanding this would tell us whether these permits are genuinely out of scope for the predictive tool or whether the data simply wasn't captured.

**On the Unknown zoning category.** After filtering to the post-2020 modeling population, 3,442 permits (15.6%) have no zoning value recorded. Is missing zoning a meaningful signal — for example, do certain permit types not require zoning assignment — or is it a data entry gap? If it's systematic, understanding which permit types drive it would help us decide whether to treat Unknown zoning as a feature value or as a flag for a different process pathway.

**On the Unknown housingcategory.** 6,878 permits in the modeling population (31.2%) have no `housingcategory`. This is the highest null rate of any high-signal feature. Is `housingcategory` only assigned to residential permits, or should all permits have a value? If it's residential-only, we can use its absence as a reliable non-residential indicator rather than treating it as missing data.

**On the review dataset coverage.** We understand that `df_review` captures correction cycle records for plans that were sent back for revisions. Can the city confirm whether approved permits ever appear in the review dataset, or whether the absence of review records is a reliable indicator that a permit's correction history is simply not exported? Specifically: are there permits that went through multiple correction cycles, were ultimately approved, and whose review records are nonetheless absent from this export?

**On the plan comments dataset.** Only 707 permits have comment records despite 40,183 permits in the post-2020 population. Is `df_comments` a partial export, or does it only capture comments from a specific review team or system? If comments exist for a broader permit population in the source system, access to a more complete export would substantially improve the NLP analysis planned as a stretch deliverable.

**On the `daysoutcorrections` field.** This field has a maximum value of 4,295 days in the raw data — nearly 12 years. Even after capping at the 99th percentile (1,005 days), the range is extreme. Does this field measure cumulative time the applicant spent making corrections across all cycles, or is it something else? Clarifying the exact definition would help us decide whether it's a legitimate complexity proxy or a field with its own data quality issues.
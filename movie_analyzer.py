import pandas as pd
import requests
import json
import os
import time
import random
import matplotlib.pyplot as plt
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# LETTERBOXD MOVIE ANALYZER - ROBUST VERSION
# ============================================================
# Put this script in the same folder as watched.csv
#
# Install:
#     pip install pandas requests matplotlib
#
# Then add your NEW TMDB API key below.
#
# IMPORTANT:
# - Do NOT post your API key publicly.
# - The script NEVER prints the API key.
# - Successful runtimes are cached immediately.
# - Failed requests are retried automatically.
# - You can stop the script with Ctrl+C and run it again.
# ============================================================

CSV_FILE = "watched.csv"
OUTPUT_FILE = "watched_with_runtimes.csv"
CACHE_FILE = "runtime_cache.json"

# Paste your NEW TMDB v3 API key here
TMDB_API_KEY = "YOUR_NEW_TMDB_API_KEY"

MAX_RETRIES = 5
REQUEST_TIMEOUT = 20
BASE_WAIT = 1


# ============================================================
# HTTP SESSION
# ============================================================

def create_session():
    """
    Creates a requests session with automatic retries for
    temporary HTTP/network failures.

    SSL verification remains ENABLED.
    """

    session = requests.Session()

    retry_strategy = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=5,
        pool_maxsize=5
    )

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


session = create_session()


# ============================================================
# LOAD MOVIES
# ============================================================

df = pd.read_csv(CSV_FILE)
df.columns = df.columns.str.strip()

print("=" * 70)
print("                 MOVIE WATCHING ANALYZER")
print("=" * 70)
print(f"Movies in CSV: {len(df)}")


# ============================================================
# LOAD CACHE
# ============================================================

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
else:
    cache = {}


def save_cache():
    """Save successful runtime lookups immediately."""
    temp_file = CACHE_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

    os.replace(temp_file, CACHE_FILE)


# ============================================================
# SAFE REQUEST
# ============================================================

def safe_get(url, params=None):
    """
    Makes a TMDB request with retries and exponential backoff.

    Errors are printed WITHOUT exposing the API key.
    """

    global session

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT
            )

            # Successful response
            if response.status_code == 200:
                return response

            # Rate limited
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")

                if retry_after:
                    wait = min(float(retry_after), 60)
                else:
                    wait = BASE_WAIT * (2 ** (attempt - 1))

                print(
                    f"      TMDB rate limit. Waiting "
                    f"{wait:.1f}s..."
                )

                time.sleep(wait)
                continue

            # Temporary server errors
            if response.status_code in [500, 502, 503, 504]:

                wait = BASE_WAIT * (2 ** (attempt - 1))

                print(
                    f"      TMDB server error "
                    f"({response.status_code}). "
                    f"Retry {attempt}/{MAX_RETRIES} "
                    f"in {wait:.1f}s..."
                )

                time.sleep(wait)
                continue

            # Authentication / permanent API error
            if response.status_code in [401, 403]:

                print(
                    f"      TMDB authentication error "
                    f"({response.status_code}). "
                    f"Check your API key."
                )

                return None

            print(
                f"      TMDB HTTP error "
                f"{response.status_code}."
            )

            return None

        except (
            requests.exceptions.SSLError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout
        ) as e:

            # Recreate the session after network/SSL failures
            session.close()
            session = create_session()

            wait = BASE_WAIT * (2 ** (attempt - 1))

            # Add a little randomness so repeated retries don't
            # happen at exactly the same moment.
            wait += random.uniform(0, 1)

            print(
                f"      Network/SSL problem. "
                f"Retry {attempt}/{MAX_RETRIES} "
                f"in {wait:.1f}s..."
            )

            time.sleep(wait)

        except Exception as e:

            print(
                f"      Unexpected request error: "
                f"{type(e).__name__}"
            )

            return None

    print("      Giving up for now; it will be retried later.")
    return None


# ============================================================
# FIND RUNTIME
# ============================================================

def get_runtime(movie_name, year):

    year_text = str(year)

    if year_text.endswith(".0"):
        year_text = year_text[:-2]

    cache_key = f"{movie_name} ({year_text})"

    # Use cached successful result
    if cache_key in cache:
        return cache[cache_key]

    # --------------------------------------------------------
    # Search TMDB
    # --------------------------------------------------------

    search_url = "https://api.themoviedb.org/3/search/movie"

    params = {
        "api_key": TMDB_API_KEY,
        "query": movie_name
    }

    if year_text and year_text != "nan":
        params["year"] = year_text

    response = safe_get(search_url, params)

    if response is None:
        return None

    try:
        results = response.json().get("results", [])
    except Exception:
        print("      Invalid response from TMDB.")
        return None

    if not results:
        print("      Movie not found on TMDB.")
        return None

    # --------------------------------------------------------
    # Choose the result with the closest release year
    # --------------------------------------------------------

    selected = results[0]

    try:
        target_year = int(float(year))

        candidates = []

        for result in results:

            release_date = result.get("release_date", "")

            if release_date:
                try:
                    result_year = int(release_date[:4])
                    candidates.append(
                        (abs(result_year - target_year), result)
                    )
                except ValueError:
                    pass

        if candidates:
            candidates.sort(key=lambda x: x[0])
            selected = candidates[0][1]

    except Exception:
        pass

    movie_id = selected.get("id")

    if not movie_id:
        return None

    # --------------------------------------------------------
    # Get movie details / runtime
    # --------------------------------------------------------

    details_url = (
        f"https://api.themoviedb.org/3/movie/{movie_id}"
    )

    details_params = {
        "api_key": TMDB_API_KEY
    }

    response = safe_get(details_url, details_params)

    if response is None:
        return None

    try:
        runtime = response.json().get("runtime")
    except Exception:
        return None

    if not runtime:
        print("      Runtime unavailable.")
        return None

    # --------------------------------------------------------
    # Save immediately
    # --------------------------------------------------------

    cache[cache_key] = runtime
    save_cache()

    return runtime


# ============================================================
# RESUME SUPPORT
# ============================================================

# If the output CSV already exists, load its known runtimes.
# This allows the script to resume after an interruption.

if os.path.exists(OUTPUT_FILE):

    try:

        previous = pd.read_csv(OUTPUT_FILE)

        if (
            "Name" in previous.columns
            and "Runtime (minutes)" in previous.columns
        ):

            previous_lookup = {}

            for _, row in previous.iterrows():

                name = str(row["Name"])

                runtime = row["Runtime (minutes)"]

                if pd.notna(runtime):

                    previous_lookup[name] = runtime

            print(
                f"Previous results found: "
                f"{len(previous_lookup)} runtimes"
            )

        else:
            previous_lookup = {}

    except Exception:
        previous_lookup = {}

else:
    previous_lookup = {}


# ============================================================
# FAST PARALLEL RUNTIME FETCHING
# ============================================================
# TMDB requires two requests per movie:
#   1. Search the movie
#   2. Get its details/runtime
#
# We use several workers concurrently instead of waiting for
# each movie to finish before starting the next one.
#
# 6 workers is a good balance between speed and avoiding
# aggressive API rate limiting.
# ============================================================

from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_WORKERS = 6


def lookup_one_movie(index):
    """Look up one movie and return (index, runtime, status)."""

    name = str(df.at[index, "Name"])
    year = df.at[index, "Year"]

    # Already completed
    if pd.notna(df.at[index, "Runtime (minutes)"]):
        return index, df.at[index, "Runtime (minutes)"], "already done"

    # Check cache first
    year_text = str(year)
    if year_text.endswith(".0"):
        year_text = year_text[:-2]

    cache_key = f"{name} ({year_text})"

    if cache_key in cache:
        return index, cache[cache_key], "cached"

    runtime = get_runtime(name, year)

    if runtime is not None:
        return index, runtime, "found"

    return index, None, "failed"


print("\n")
print("=" * 70)
print(f"       FAST MODE — {MAX_WORKERS} PARALLEL WORKERS")
print("=" * 70)
print("Starting runtime lookups...\n")

# Make sure the column exists
if "Runtime (minutes)" not in df.columns:
    df["Runtime (minutes)"] = pd.NA

# Identify movies that actually need a lookup
pending_indices = [
    i for i in df.index
    if pd.isna(df.at[i, "Runtime (minutes)"])
]

print(
    f"Movies already completed: "
    f"{len(df) - len(pending_indices)}"
)
print(
    f"Movies needing lookup:    "
    f"{len(pending_indices)}"
)
print()

failed_movies = []

completed = len(df) - len(pending_indices)
total = len(df)

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

    futures = {
        executor.submit(lookup_one_movie, i): i
        for i in pending_indices
    }

    for future in as_completed(futures):

        index = futures[future]

        try:
            index, runtime, status = future.result()

            name = str(df.at[index, "Name"])

            if runtime is not None:
                df.at[index, "Runtime (minutes)"] = runtime
            else:
                failed_movies.append(index)

            completed += 1

            if runtime is not None:
                print(
                    f"[{completed:>3}/{total}] "
                    f"{name} → {int(float(runtime))} min "
                    f"({status})"
                )
            else:
                print(
                    f"[{completed:>3}/{total}] "
                    f"{name} → FAILED"
                )

            # Save progress periodically rather than after every
            # movie. This is much faster with parallel requests.
            if completed % 10 == 0:
                df.to_csv(OUTPUT_FILE, index=False)

        except Exception as e:

            completed += 1
            failed_movies.append(index)

            print(
                f"[{completed:>3}/{total}] "
                f"{df.at[index, 'Name']} → "
                f"ERROR: {type(e).__name__}"
            )

# Save all progress
df.to_csv(OUTPUT_FILE, index=False)


# ============================================================
# RETRY FAILED MOVIES
# ============================================================

if failed_movies:

    print("\n")
    print("=" * 70)
    print(
        f"RETRYING {len(failed_movies)} FAILED MOVIES"
    )
    print("=" * 70)

    second_failed = []

    # Retry concurrently too, but use fewer workers to be gentle
    # after a batch of failures.
    retry_workers = 3

    with ThreadPoolExecutor(max_workers=retry_workers) as executor:

        futures = {
            executor.submit(lookup_one_movie, i): i
            for i in failed_movies
        }

        for future in as_completed(futures):

            index = futures[future]

            try:
                index, runtime, status = future.result()

                name = str(df.at[index, "Name"])

                if runtime is not None:
                    df.at[index, "Runtime (minutes)"] = runtime

                    print(
                        f"[RETRY OK] {name} → "
                        f"{int(float(runtime))} min"
                    )

                else:
                    second_failed.append(index)

                    print(
                        f"[RETRY FAILED] {name}"
                    )

            except Exception:
                second_failed.append(index)

    failed_movies = second_failed

    df.to_csv(OUTPUT_FILE, index=False)


# ============================================================
# FINAL STATISTICS
# ============================================================

valid = pd.to_numeric(
    df["Runtime (minutes)"],
    errors="coerce"
).dropna()

total_movies = len(df)
movies_with_runtime = len(valid)
movies_missing_runtime = total_movies - movies_with_runtime

total_minutes = valid.sum()
total_hours = total_minutes / 60
total_days = total_hours / 24

average_runtime = valid.mean()
median_runtime = valid.median()

print("\n")
print("=" * 70)
print("                    YOUR MOVIE STATS")
print("=" * 70)

print(f"\nMovies watched:          {total_movies:,}")
print(f"Runtimes found:          {movies_with_runtime:,}")
print(f"Runtimes missing:        {movies_missing_runtime:,}")

print("\nTIME SPENT WATCHING")
print("-" * 70)

print(f"Total minutes:           {total_minutes:,.0f}")
print(f"Total hours:             {total_hours:,.2f}")
print(f"Total days:              {total_days:,.2f}")

whole_days = int(total_days)
remaining_hours = total_hours - whole_days * 24

print(
    f"That's approximately:    "
    f"{whole_days} days and "
    f"{remaining_hours:.1f} hours"
)

print("\nMOVIE LENGTH")
print("-" * 70)

print(
    f"Average movie:           "
    f"{average_runtime:.1f} minutes"
)

print(
    f"Median movie:            "
    f"{median_runtime:.1f} minutes"
)


# ============================================================
# LONGEST / SHORTEST
# ============================================================

if len(valid) > 0:

    longest_index = valid.idxmax()
    shortest_index = valid.idxmin()

    longest_movie = df.loc[longest_index, "Name"]
    shortest_movie = df.loc[shortest_index, "Name"]

    longest_runtime = df.loc[
        longest_index, "Runtime (minutes)"
    ]

    shortest_runtime = df.loc[
        shortest_index, "Runtime (minutes)"
    ]

    print(
        f"Longest movie:           "
        f"{longest_movie} "
        f"({int(longest_runtime)} min)"
    )

    print(
        f"Shortest movie:          "
        f"{shortest_movie} "
        f"({int(shortest_runtime)} min)"
    )


# ============================================================
# YEARLY ANALYSIS
# ============================================================

df["Date"] = pd.to_datetime(
    df["Date"],
    errors="coerce"
)

df["Watch Year"] = df["Date"].dt.year

yearly = (
    df.dropna(subset=["Watch Year"])
      .groupby("Watch Year")
      .agg(
          Movies=("Name", "count"),
          Minutes=("Runtime (minutes)", "sum")
      )
)

yearly["Hours"] = yearly["Minutes"] / 60

print("\n")
print("=" * 70)
print("                  WATCHING BY YEAR")
print("=" * 70)

print(
    yearly[["Movies", "Hours"]]
    .round(2)
    .to_string()
)


if len(yearly) > 0:

    most_movies_year = yearly["Movies"].idxmax()

    most_movies_count = yearly.loc[
        most_movies_year, "Movies"
    ]

    most_hours_year = yearly["Hours"].idxmax()

    most_hours = yearly.loc[
        most_hours_year, "Hours"
    ]

    print(
        f"\nMost movies in one year: "
        f"{int(most_movies_year)} → "
        f"{int(most_movies_count)} movies"
    )

    print(
        f"Most hours in one year:  "
        f"{int(most_hours_year)} → "
        f"{most_hours:.1f} hours"
    )


# ============================================================
# MONTHLY ANALYSIS
# ============================================================

df["Month"] = df["Date"].dt.month

monthly = (
    df.dropna(subset=["Month"])
      .groupby("Month")
      .size()
)

month_names = [
    "January", "February", "March", "April",
    "May", "June", "July", "August",
    "September", "October", "November", "December"
]

print("\n")
print("=" * 70)
print("                  WATCHING BY MONTH")
print("=" * 70)

for month_number in range(1, 13):

    count = monthly.get(month_number, 0)

    print(
        f"{month_names[month_number - 1]:<12}"
        f"{count:>4} movies"
    )


# ============================================================
# RUNTIME CATEGORIES
# ============================================================

def runtime_category(minutes):

    if pd.isna(minutes):
        return "Unknown"

    if minutes < 90:
        return "Under 90 min"

    if minutes < 120:
        return "90–119 min"

    if minutes < 150:
        return "120–149 min"

    if minutes < 180:
        return "150–179 min"

    return "180+ min"


df["Runtime Category"] = (
    df["Runtime (minutes)"]
    .apply(runtime_category)
)

categories = [
    "Under 90 min",
    "90–119 min",
    "120–149 min",
    "150–179 min",
    "180+ min"
]

print("\n")
print("=" * 70)
print("                 MOVIE LENGTH BREAKDOWN")
print("=" * 70)

for category in categories:

    count = (
        df["Runtime Category"] == category
    ).sum()

    percentage = (
        count / movies_with_runtime * 100
        if movies_with_runtime
        else 0
    )

    print(
        f"{category:<15}"
        f"{count:>4} movies "
        f"({percentage:>5.1f}%)"
    )


# ============================================================
# FAILED MOVIES
# ============================================================

if failed_movies:

    print("\n")
    print("=" * 70)
    print("                    STILL MISSING")
    print("=" * 70)

    print(
        f"{len(failed_movies)} movies could not be "
        f"looked up automatically:"
    )

    for index in failed_movies:
        print(
            f"  - {df.loc[index, 'Name']} "
            f"({df.loc[index, 'Year']})"
        )

else:

    print("\nAll movie runtimes were successfully found!")


# ============================================================
# SAVE FINAL CSV
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print(
    f"\nSaved: {OUTPUT_FILE}"
)


# ============================================================
# GRAPHS
# ============================================================

if len(yearly) > 0:

    # Movies per year
    plt.figure(figsize=(12, 6))

    plt.bar(
        yearly.index.astype(int).astype(str),
        yearly["Movies"]
    )

    plt.title("Movies Watched Per Year")
    plt.xlabel("Year")
    plt.ylabel("Number of Movies")

    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig(
        "movies_per_year.png",
        dpi=200
    )

    plt.show()


    # Hours per year
    plt.figure(figsize=(12, 6))

    plt.bar(
        yearly.index.astype(int).astype(str),
        yearly["Hours"]
    )

    plt.title("Hours Spent Watching Movies Per Year")
    plt.xlabel("Year")
    plt.ylabel("Hours")

    plt.xticks(rotation=45)
    plt.tight_layout()

    plt.savefig(
        "hours_per_year.png",
        dpi=200
    )

    plt.show()


# Runtime distribution
if len(valid) > 0:

    plt.figure(figsize=(10, 6))

    plt.hist(
        valid,
        bins=20
    )

    plt.title("Distribution of Movie Runtimes")
    plt.xlabel("Runtime (minutes)")
    plt.ylabel("Number of Movies")

    plt.tight_layout()

    plt.savefig(
        "runtime_distribution.png",
        dpi=200
    )

    plt.show()


# ============================================================
# FINAL MESSAGE
# ============================================================

print("\n")
print("=" * 70)
print("                         DONE!")
print("=" * 70)

print(
    f"\nYou have spent approximately "
    f"{total_hours:,.1f} HOURS watching movies."
)

print(
    f"That's {total_days:,.2f} full DAYS of your life "
    f"spent watching movies."
)

print("\nGenerated:")
print(f"  {OUTPUT_FILE}")
print("  movies_per_year.png")
print("  hours_per_year.png")
print("  runtime_distribution.png")
print("  runtime_cache.json")

print("\nYou can safely run this script again.")
print("Successful runtimes will be reused from the cache.")

# Rep transcript

## Session 2026-09-20, evening window

### Rep 1 - process-kdd-loop (L3, explain) - correct, no help

**Q:** Leo in Marketing Ops has you cluster last quarter's 38 campaigns by cost per lead. At
pattern evaluation, the cheapest cluster is 9 campaigns at under $0.40 per lead. You dig in:
those 9 are the same 3 campaigns, each one loaded once per ad platform, so the spend is split
three ways but every lead is counted three times. Which KDD step do you go back to, and why
that one?

**Your answer:** By cluster that means group, so we did a group-by on cost with the count being
leads? We evaluated the pattern, which is step 6, and found the cheapest group to be 9 campaigns
at $0.40, but the 9 campaigns are actually 3. I don't like assumptions, but I'll assume we have
3 ad platforms, and in that case we are duplicating data, so we need to go clean our data, which
should be step 2.

**My answer:** Right: evaluation sent you back to cleaning, because a lead counted three times
is a data problem, not a pattern. Cleaning is step 1 in your notes and integration is step 2,
and here either defends itself, since the duplicates were born when three platform exports got
stitched together. Naming the assumption out loud is the right move, not a weakness, and yes,
cluster means group, done by a mining technique at step 5.

### Rep 2 - process-crisp-dm (L3, explain) - correct, one guiding question

**Q:** Dana in Finance wants a model that flags invoices likely to be paid late. You have 15
working days. A teammate hands you this plan: 1 day with Dana's team, 2 days looking at the
data, 2 days cleaning and building features, 7 days on the model, 2 days on error metrics,
1 day shipping it. Using CRISP-DM, which stage is underbooked, and which stage should the extra
days come from?

**Your answer:** Based on how often this phase is overlooked in leadership, and knowing it is
about 70-80% of the work, the data cleaning and feature building section is the weakest, mostly
around data cleaning and looking at the data (data discovery). [After a guiding question:] It's
the modeling process. I'd go 1 day for meetings (business understanding) and keep asking
questions throughout as I see new things in the data or the model moves, 2 days for data
understanding, a week for data preparation, 2 days for modeling, a day for evaluation, and about
a day to push to prod, and those last two can swap time since testing generally allows better
deployment. [Correction:] I missed a day, put it in model evaluation.

**My answer:** Modeling is right: 7 of 15 days on the model is the classic mistake, and your
rebuilt plan names all six stages in order. Keeping business understanding running throughout
instead of spending it on day 1 matches how CRISP-DM actually behaves, since evaluation sends you
back to Dana with questions. With the extra day in evaluation your rebuild adds to 13 days if a week
means 5 working days, or 15 if you meant 7, so say which and the plan closes.

### Rep 3 - tools-spark-memory (L3, explain) - correct, no help

**Q:** Priya's nightly vendor lead-time job reads 2 TB on a Hadoop cluster with MapReduce and
takes 40 minutes. It filters down to the last 90 days once, then walks that same filtered set
five times to build five warehouse reports. A vendor is pitching a move to Spark. What about
Spark's design makes those five passes faster, and what has to be on the machine before your
PySpark script will even start?

**Your answer:** Right now we use Hadoop, which I don't know much about except it would write to
disk and have to read off to put back in memory, so it was slow, and I think sequential too.
Spark allows parallel processing by processing entirely in RAM across parallel nodes. I need Java
on my machine before anything, because I think it was built in Scala.

**My answer:** Both halves right: Spark holds the filtered 90 days in memory across the cluster,
so passes two through five skip the disk entirely, and PySpark needs a JVM because Spark is
written in Scala, which compiles to Java bytecode. The one thing to correct is sequential:
MapReduce is parallel too, across many machines at once. What it lacks is memory between steps,
so every stage writes its result to disk and the next stage reads it back, which is the round
trip your five passes pay five times.

### Rep 4 - env-uv-sync (L3, explain) - wrong, then fixed

**Q:** Sam brings on a contractor for the lead-enrichment work. They clone this repo, run
`pip install pandas numpy scikit-learn`, and a line in your notebook that works on your machine
throws an error on theirs. What one command should they have run instead, and which file decides
the versions it installs?

**Your answer:** They should have run `uv sync` if they cloned this repo, and the file that
decides is the `pyproject.toml` file. [After the correction:] It keeps track of the dependencies,
python versions, and information about the repo, and acts as a way for uv to install from so that
uv.lock can track everything and put it in the .venv.

**My answer:** `uv sync` is right, but the file is `uv.lock`. `pyproject.toml` states a wish, a
range like `pandas>=2.0` plus `requires-python` and the repo's own information, and a range
resolves to a different version depending on the day you run it. `uv.lock` records the decision
that resolution already made, one exact version per package, and `uv sync` builds `.venv` from
it, which is why the contractor's environment matches yours down to the patch number. Your
follow-up walked that chain correctly, so it counts as a fix.

## 2026-09-21-1051

### Rep 1 - env-uv-sync (L2, fill) - correct, no help

**Q:** Marcus's new sales ops analyst is setting up the lead-scoring repo on a fresh laptop. The
runbook has one step blanked out. Type the missing line, and name the file it reads to decide
which pandas version lands in `.venv`.

```
git clone git@github.com:cobalt-trail/pipeline-reports.git
cd pipeline-reports
______________
uv run python scripts/score_leads.py
```

**Your answer:** The line missing is `uv sync`. It should read the `uv.lock` file to understand
the version of any library that needs to be in the `.venv`, because the `uv.lock` file is
explicit unlike the `pyproject.toml` files.

**My answer:** Both halves right, and "explicit" is the word that carries it: `uv.lock` names one
exact version per package, `pyproject.toml` names a range. That is the piece that was missing on
2026-09-20, so the skill is back at L3.

### Rep 2 - np-dtype-casts (L1, predict) - correct, no help

**Q:** Dana sends over a spend extract and wants to know what these two lines do before she trusts
them. What does each line print?

```python
spend = np.array([1299.75, 840.20, 0.0, 17.99])
print(spend.astype(int))
print(spend.astype(bool))
```

**Your answer:** int should just print 1299, 840, 0, 17 (because it just strips the whole number),
and bool will be T, T, F, T except they will actually say True and False. Anything outside of 0 is
True.

**My answer:** Both right, including the reason bool gives True for anything nonzero. The
sharpening: it truncates toward zero rather than dropping digits, so a credit memo of -17.99
becomes -17, not -18, which in finance data moves money the wrong way.

### Rep 3 - np-one-dtype (L1, predict) - wrong, then fixed

**Q:** Priya pulls vendor lead times and a SKU list into arrays. What does each dtype come back as?

```python
lead = np.array([7, 14, 21.5])
print(lead.dtype)

sku = np.array([5, "TENT-22", 3.0])
print(sku.dtype)
```

**Your answer:** Both types are not the same or homogeneous, so I am going to say a type error will
form. [After the model:] lead will be a float and sku will be a string type. For the float I would
say float64 since it's the most general, but for data sizing float16?

**My answer:** The homogeneous part was right, and that is why there is no error: an array is one
block of memory with one type, so NumPy picks a type that can hold every value and converts the
whole thing. Refusing would leave it nothing to store. Ints with floats land on float64, and
anything mixed with text lands on text (`<U32`, meaning Unicode up to 32 characters), so the
numbers become the strings '5' and '3.0'.

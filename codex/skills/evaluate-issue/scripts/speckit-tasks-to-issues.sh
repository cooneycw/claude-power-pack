#!/usr/bin/env bash
#
# speckit-tasks-to-issues.sh - Create GitHub issues from a spec-kit tasks.md
# using the gh CLI (CPP's Option-B sync; no github-mcp-server required).
#
# Part of Claude Power Pack (CPP). Replaces upstream /speckit-taskstoissues, which
# hard-requires the github-mcp-server. CPP is gh-CLI based, so this reproduces the
# same behaviour with `gh`:
#   - one issue per task, titled "T001 (<feature>): <description>"
#   - every issue carries a FEATURE-SCOPED identity marker, so re-runs are safe
#     and two features' T001 are different tasks (issue #857)
#   - refuses to run unless the git remote is a GitHub URL
#
# Usage:
#   scripts/speckit-tasks-to-issues.sh [--dry-run] [--tasks PATH] [--repo OWNER/NAME]
#                                      [--feature SLUG] [--limit N]
#
# Options:
#   --dry-run        Print what would be created; create nothing.
#   --tasks PATH     Path to tasks.md. Default: auto-detect the single
#                    .specify/specs/*/tasks.md, else error.
#   --repo OWNER/NM  Target repo for gh (default: the origin remote's repo).
#   --feature SLUG   Feature identity for these tasks. Default: the tasks file's
#                    repository-relative path. If the file MOVES, pass the value
#                    the existing issues were filed under - the ORIGINAL path -
#                    or they are no longer recognised and get filed again. A new
#                    slug does not prevent that; only the original identity does.
#   --limit N        Issues to scan for the existing-work inventory (default 1000).
#   -h, --help       Show this help.
#
# Exit codes:
#   0  success
#   1  environment refusal (no gh, no GitHub remote, no tasks file)
#   2  usage error
#   3  tasks.md could not be parsed (malformed task lines, or no tasks at all)
#   4  the existing-issue inventory could not be established (lookup failed, or
#      the result may be truncated)
#   5  one or more tasks have an ambiguous legacy identity awaiting resolution
#   6  issues were created but a dependency edge could not be written; re-run to
#      reconcile
set -euo pipefail

DRY_RUN=0
TASKS=""
REPO=""
FEATURE=""
LIMIT=1000

usage() { sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1; shift ;;
        --tasks) TASKS="${2:?--tasks needs a path}"; shift 2 ;;
        --repo) REPO="${2:?--repo needs OWNER/NAME}"; shift 2 ;;
        --feature) FEATURE="${2:?--feature needs a slug}"; shift 2 ;;
        --limit) LIMIT="${2:?--limit needs a number}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

[[ "$LIMIT" =~ ^[0-9]+$ ]] && [ "$LIMIT" -gt 0 ] || {
    echo "ERROR: --limit must be a positive integer (got '$LIMIT')." >&2; exit 2; }

command -v gh > /dev/null 2>&1 || { echo "ERROR: gh CLI not found." >&2; exit 1; }
command -v jq > /dev/null 2>&1 || { echo "ERROR: jq not found." >&2; exit 1; }

# --- Safety: only operate against a GitHub remote --------------------------------
REMOTE_URL="$(git config --get remote.origin.url 2>/dev/null || true)"
if [ -z "$REMOTE_URL" ]; then
    echo "ERROR: no git remote 'origin' found. Refusing to create issues." >&2
    exit 1
fi
case "$REMOTE_URL" in
    *github.com[:/]*) : ;;   # ok: https://github.com/o/r(.git) or git@github.com:o/r.git
    *) echo "ERROR: remote is not a GitHub URL ($REMOTE_URL). Refusing." >&2; exit 1 ;;
esac

# --- Locate tasks.md -------------------------------------------------------------
if [ -z "$TASKS" ]; then
    mapfile -t _candidates < <(find .specify/specs -maxdepth 2 -name tasks.md 2>/dev/null | sort)
    if [ "${#_candidates[@]}" -eq 0 ]; then
        echo "ERROR: no .specify/specs/*/tasks.md found. Pass --tasks PATH." >&2
        exit 1
    elif [ "${#_candidates[@]}" -gt 1 ]; then
        echo "ERROR: multiple tasks.md found; disambiguate with --tasks PATH:" >&2
        printf '  %s\n' "${_candidates[@]}" >&2
        exit 1
    fi
    TASKS="${_candidates[0]}"
fi
[ -f "$TASKS" ] || { echo "ERROR: tasks file not found: $TASKS" >&2; exit 1; }

# --- Feature identity (issue #857) -----------------------------------------------
# A task ID is only unique WITHIN a feature: every feature starts again at T001, so
# "T001" alone identified nothing and one feature's T001 issue made every other
# feature's T001 look already-filed.
#
# Identity is therefore the pair (feature, task id), and the feature half has to be
# something that cannot collapse two different tasks files into one identity. The
# tasks file's REPOSITORY-RELATIVE PATH is that: unique by construction, stable
# across re-runs, and derivable without asking. A human heading is deliberately NOT
# used - two specs may both be titled "# Tasks: Reporting", and the collision would
# be silent. `--feature` overrides it, which is also how identity survives the file
# being moved or renamed later - but only when it carries the value those issues
# were filed under. Passing some other slug after a move does not preserve
# anything: it declares a new identity, and every task is filed a second time.
TASKS_REL="$TASKS"
if _repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" && [ -n "$_repo_root" ]; then
    _tasks_abs="$(cd "$(dirname "$TASKS")" && pwd)/$(basename "$TASKS")"
    case "$_tasks_abs" in
        "$_repo_root"/*) TASKS_REL="${_tasks_abs#"$_repo_root"/}" ;;
        *) TASKS_REL="$_tasks_abs" ;;
    esac
fi
if [ -z "$FEATURE" ]; then
    FEATURE="$TASKS_REL"
fi
case "$FEATURE" in
    *$'\n'*|"") echo "ERROR: feature identity is empty or multi-line; pass --feature SLUG." >&2; exit 2 ;;
esac

GH_REPO_ARGS=()
[ -n "$REPO" ] && GH_REPO_ARGS=(--repo "$REPO")

echo "Tasks file: $TASKS"
echo "Feature:    $FEATURE"
echo "Remote:     $REMOTE_URL"
[ "$DRY_RUN" -eq 1 ] && echo "Mode:       DRY RUN (no issues will be created)"

marker_for() { printf '<!-- speckit-task:v1:%s:%s -->' "$FEATURE" "$1"; }
provenance_for() { printf 'Auto-created from %s (%s) by CPP speckit-tasks-to-issues.' "$TASKS" "$1"; }

# --- Pass 1: parse tasks.md ------------------------------------------------------
# Parsing runs to completion BEFORE any issue is created: a file this script cannot
# read is a failure to report, not a zero-task success to celebrate (issue #857).
#
# Both ID spellings the shipped templates use are accepted. `.specify/templates/
# tasks-template.md` writes the BOLD form (`- [ ] **T001** [US1] ...`), which the
# original strict-plain parser skipped silently - so the converter could not read
# the template this repository ships. Story tags are stripped in both the single
# (`[US1]`) and comma (`[US1,US2]`, `[US1, US2]`) spellings; the comma form is on
# the template's own T007 line and used to leak into the issue title.
declare -a TIDS=() DESCS=() DEPS=()
declare -A SEEN_TID=()
declare -a MALFORMED=() UNRECOGNISED=()
lineno=0
while IFS= read -r line || [ -n "$line" ]; do
    lineno=$((lineno + 1))
    [[ "$line" =~ ^[[:space:]]*-[[:space:]]*\[[[:space:]xX]\] ]] || continue
    body="${line#*] }"
    body="$(printf '%s' "$body" | sed -E 's/\[P\]//g; s/\[US[0-9]+([[:space:]]*,[[:space:]]*US?[0-9]+)*\]//gI; s/^[[:space:]]+//')"
    body="$(printf '%s' "$body" | sed -E 's/^(\*\*|__)[[:space:]]*(T[0-9]{3})[[:space:]]*(\*\*|__)/\2/')"
    if [[ "$body" =~ ^(T[0-9]{3})([:[:space:]]+(.*))?$ ]]; then
        tid="${BASH_REMATCH[1]}"
        desc="$(printf '%s' "${BASH_REMATCH[3]:-}" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
        if [ -z "$desc" ]; then
            MALFORMED+=("${TASKS}:${lineno}: ${tid} has no description: ${line}")
            continue
        fi
        if [ -n "${SEEN_TID[$tid]:-}" ]; then
            MALFORMED+=("${TASKS}:${lineno}: duplicate task id ${tid} in this feature: ${line}")
            continue
        fi
        SEEN_TID["$tid"]=1
        dep_list=""
        if [[ "$desc" =~ \(depends\ on\ ([^\)]*)\) ]]; then
            dep_clause="${BASH_REMATCH[1]}"
            # Validate WHOLE tokens, never substrings. Extracting `T[0-9]{3}` out
            # of the clause silently accepted two corruptions: `T002, T1` dropped
            # the invalid half and wrote a partial edge, and `T0020` matched its
            # own first four characters and wrote an edge to T002 - a dependency
            # that was never declared. A fabricated edge is worse than a missing
            # one, because the planner treats it as a real constraint.
            #
            # Supported syntax is comma- and/or space-separated task ids, with
            # `and` tolerated as a connector (the same separator the planner's
            # own edge grammar accepts). Anything else is reported with its line
            # rather than quietly dropped.
            dep_bad=""
            for dep_token in $(printf '%s' "$dep_clause" | tr ',' ' '); do
                case "$dep_token" in
                    and|AND|And) continue ;;
                esac
                if [[ "$dep_token" =~ ^T[0-9]{3}$ ]]; then
                    case " $dep_list" in
                        *" $dep_token "*) continue ;;
                    esac
                    dep_list+="$dep_token "
                else
                    dep_bad+="'${dep_token}' "
                fi
            done
            dep_list="${dep_list%"${dep_list##*[![:space:]]}"}"
            if [ -n "$dep_bad" ]; then
                MALFORMED+=("${TASKS}:${lineno}: dependency clause '(depends on ${dep_clause})' has unreadable token(s) ${dep_bad}(expected T001..T999): ${line}")
                continue
            fi
            if [ -z "$dep_list" ]; then
                MALFORMED+=("${TASKS}:${lineno}: dependency clause '(depends on ${dep_clause})' names no task id (expected T001..T999): ${line}")
                continue
            fi
        fi
        TIDS+=("$tid"); DESCS+=("$desc"); DEPS+=("$dep_list")
    elif [[ "$body" =~ (^|[^A-Za-z0-9])T[0-9]+([^A-Za-z0-9]|$) ]]; then
        # Carries a T-number that is not a valid task id (T1, T12, T0001 ...).
        # Silently skipping these is how a file of malformed tasks reported
        # "0 to create" and exited 0.
        MALFORMED+=("${TASKS}:${lineno}: task-like line with a malformed T-number (expected T001..T999): ${line}")
    else
        # A checkbox line with no T-number at all. It may be a legitimate non-task
        # checkbox, so it does not fail the run on its own - but it is never
        # swallowed either, and a file where EVERY line lands here still fails
        # below on the zero-task check rather than reporting a successful nothing.
        UNRECOGNISED+=("${TASKS}:${lineno}: checkbox line is not a task and was ignored: ${line}")
    fi
done < "$TASKS"

if [ "${#UNRECOGNISED[@]}" -gt 0 ]; then
    echo "NOTE: ${#UNRECOGNISED[@]} checkbox line(s) were not read as tasks:" >&2
    printf '  %s\n' "${UNRECOGNISED[@]}" >&2
fi

if [ "${#MALFORMED[@]}" -gt 0 ]; then
    echo "ERROR: ${#MALFORMED[@]} task-like line(s) could not be parsed:" >&2
    printf '  %s\n' "${MALFORMED[@]}" >&2
    echo "Fix the lines above (or pass a different --tasks) and re-run. No issues were created." >&2
    exit 3
fi
if [ "${#TIDS[@]}" -eq 0 ]; then
    echo "ERROR: no tasks found in ${TASKS}." >&2
    echo "Expected checkbox lines such as '- [ ] **T001** [US1] Description'." >&2
    exit 3
fi
echo "Parsed:     ${#TIDS[@]} task(s)"

# --- Inventory of existing issues ------------------------------------------------
# ISSUE_FS - the ONE field separator for the `gh issue list` records parsed below
# (issue #700), ASCII unit separator (0x1F) and deliberately NOT tab.
#
# Tab is IFS *whitespace*, so shell field splitting collapses a run of it into a
# single delimiter and an EMPTY field vanishes rather than arriving empty - every
# later field shifts up one slot. This loop shipped with tab, and was safe only by
# accident: field 1 is `.number`, and a GitHub issue always has one, so the
# empty-first-field case could not arise from the input source. That safety was a
# property of an external tool's output, held about a call site two lines away and
# recorded nowhere - it decays the moment the query gains a field, the field order
# changes, or a filter that can emit empty is introduced, and it decays into
# SHIFTED FIELDS (issue bodies built from the wrong values), not an error.
# `\037` is not IFS whitespace, so empty fields survive in every position.
#
# That is exactly what happened here: #857 added three more fields, and two of them
# (marker, provenance path) are EMPTY for every issue this script did not create.
#
# Same defect class as #698, which fixed the live instance in
# scripts/flow-wave-registry.sh (a branchless worktree produced an empty middle
# field on the ordinary path).
#
# ONE definition, two spellings: the producer is a jq filter needing the `\uHHHH`
# escape text, the reader is a shell `read` needing the byte, so the escape is
# DERIVED from the byte rather than written out a second time. Four independent
# definitions of the separator were what made #698 possible, and the failure mode
# is silent, so a drifted copy would not announce itself.
ISSUE_FS="$(printf '\037')"
ISSUE_FS_JQ="$(printf '\\u%04x' "'$ISSUE_FS")"
if [ "${#ISSUE_FS}" -ne 1 ] || [ "${#ISSUE_FS_JQ}" -ne 6 ]; then
    echo "ERROR: could not derive the field separator (got a ${#ISSUE_FS}-char byte," \
         "${#ISSUE_FS_JQ}-char escape). Refusing to parse with an unknown delimiter." >&2
    exit 1
fi

# Record: number FS marker FS provenance-path FS legacy-tid FS blocked-refs
# marker         - the speckit-task identity comment, when the body carries one
# provenance     - the tasks path recorded in the "Auto-created from ..." line, which
#                  is the only feature evidence a pre-#857 issue carries
# legacy-tid     - a bare T-number in the TITLE, the pre-#857 identity
# blocked-refs   - "#N" refs already present on this body's `Blocked by` lines, so a
#                  re-run can tell a missing edge from one already written
INVENTORY_JQ='
.[] |
  (.body // "") as $b |
  ($b | capture("<!--\\s*(?<m>speckit-task:v1:[^>]*?)\\s*-->") // {m:""} | .m) as $marker |
  ($b | capture("Auto-created from (?<p>.+?) \\(T[0-9]{3}\\) by CPP speckit-tasks-to-issues") // {p:""} | .p) as $prov |
  ((.title // "") | capture("(^|[^A-Za-z0-9])(?<t>T[0-9]{3})([^0-9]|$)") // {t:""} | .t) as $ltid |
  ([$b | scan("(?im)^\\s*[-*]?\\s*blocked by[^#\\n]*(#[0-9]+)") | .[0]] | join(",")) as $refs |
  "\(.number)FS\($marker)FS\($prov)FS\($ltid)FS\($refs)"
'
INVENTORY_JQ="${INVENTORY_JQ//FS/$ISSUE_FS_JQ}"

inventory_raw=""
inventory_status=0
inventory_raw="$(gh issue list "${GH_REPO_ARGS[@]}" --state all --limit "$LIMIT" \
    --json number,title,body --jq "$INVENTORY_JQ" 2>&1)" || inventory_status=$?
if [ "$inventory_status" -ne 0 ]; then
    echo "ERROR: could not list existing issues (gh exited ${inventory_status})." >&2
    printf '  %s\n' "$inventory_raw" >&2
    echo "Refusing to continue: an unreadable inventory is not an empty one, and treating" >&2
    echo "it as empty re-files every task that already has an issue." >&2
    exit 4
fi

declare -A FILED_NUM=()       # tid -> issue number claimed for THIS feature
declare -A FILED_VIA=()       # tid -> marker | provenance
declare -A EXISTING_REFS=()   # tid -> "#12,#13" already on the issue body
declare -A MARKER_CLAIMS=()   # tid -> "#N #M" issues whose marker names this feature
declare -A PROV_CLAIMS=()     # tid -> "#N #M" issues whose recorded source is this file
declare -A UNRESOLVED_HITS=() # tid -> "#N" bare-title issues carrying no feature evidence
inventory_count=0
while IFS="$ISSUE_FS" read -r number marker prov ltid refs; do
    [ -n "$number" ] || continue
    inventory_count=$((inventory_count + 1))
    if [ -n "$marker" ]; then
        # Exact identity. A marker naming a DIFFERENT feature is a known other
        # task, not a claim on this one.
        #
        # The comparison is EXACT, never a prefix: a feature may legitimately
        # contain a colon (`--feature f:other`), so testing `speckit-task:v1:f:*`
        # accepts `speckit-task:v1:f:other:T001` and hands one feature's task to
        # another. Split the last field off as the task id and compare what
        # remains to this feature in full.
        marker_rest="${marker#speckit-task:v1:}"
        if [ "$marker_rest" != "$marker" ]; then
            tid="${marker_rest##*:}"
            marker_feature="${marker_rest%:*}"
            if [[ "$tid" =~ ^T[0-9]{3}$ ]] && [ "$marker_feature" = "$FEATURE" ]; then
                MARKER_CLAIMS["$tid"]="${MARKER_CLAIMS[$tid]:-}#${number} "
                FILED_NUM["$tid"]="$number"
                FILED_VIA["$tid"]="marker"
                EXISTING_REFS["$tid"]="$refs"
            fi
        fi
        continue
    fi
    [ -n "$ltid" ] || continue
    if [ -n "$prov" ]; then
        if [ "$prov" = "$TASKS" ] || [ "$prov" = "$TASKS_REL" ]; then
            # A pre-#857 issue this script created from THIS tasks file. The
            # recorded source path is real feature provenance, so adopting it is
            # evidence, not a guess.
            PROV_CLAIMS["$ltid"]="${PROV_CLAIMS[$ltid]:-}#${number} "
            if [ -z "${FILED_NUM[$ltid]:-}" ]; then
                FILED_NUM["$ltid"]="$number"
                FILED_VIA["$ltid"]="provenance"
                EXISTING_REFS["$ltid"]="$refs"
            fi
        fi
        # A provenance line naming a DIFFERENT tasks file is a known different
        # feature. It says nothing about this feature's task of the same number,
        # so it must not block this one from being filed.
        continue
    fi
    # A bare T-number in a title, with no marker and no recorded source at all.
    # Whose task it is cannot be established: two features routinely share both a
    # task id AND its description ("T001 Add tests"), so a description match is not
    # provenance. Recorded as unresolved and settled by a human, never guessed.
    UNRESOLVED_HITS["$ltid"]="${UNRESOLVED_HITS[$ltid]:-}#${number} "
done <<< "$inventory_raw"

if [ "$inventory_count" -ge "$LIMIT" ]; then
    echo "ERROR: the issue inventory returned ${inventory_count} record(s), the same as" >&2
    echo "--limit ${LIMIT}. The list may be truncated, and a truncated inventory cannot" >&2
    echo "support the re-run guarantee: a task whose issue fell past the cutoff would be" >&2
    echo "filed a second time. Re-run with a larger --limit." >&2
    exit 4
fi
echo "Inventory:  ${inventory_count} issue(s) scanned (limit ${LIMIT})"

# --- Ambiguity scan: everything that must stop the run happens BEFORE any write ---
declare -a AMBIGUOUS=()
for i in "${!TIDS[@]}"; do
    tid="${TIDS[$i]}"
    # Count DISTINCT issues claiming this feature's task, whatever kind of claim
    # they carry. Counting each bucket separately misses the mixed case - one
    # issue with the marker and a different issue whose recorded source is this
    # tasks file - which is two issues claiming one task and is exactly as
    # ambiguous as two of either kind. The same issue appearing in both buckets
    # cannot happen (a marker short-circuits the provenance read), so a repeat
    # number here is always two different records.
    claimants="$(printf '%s %s' "${MARKER_CLAIMS[$tid]:-}" "${PROV_CLAIMS[$tid]:-}" | tr ' ' '\n' | grep -c '^#[0-9]' || true)"
    if [ "$claimants" -gt 1 ]; then
        AMBIGUOUS+=("${tid}: ${claimants} issues claim this feature's task: marker ${MARKER_CLAIMS[$tid]:-none} / recorded source ${PROV_CLAIMS[$tid]:-none}")
        continue
    fi
    # An identified task is not made ambiguous by somebody else's untraceable
    # issue: this feature's task already has evidence naming it.
    [ -n "${FILED_NUM[$tid]:-}" ] && continue
    [ -n "${UNRESOLVED_HITS[$tid]:-}" ] || continue
    AMBIGUOUS+=("${tid}: ${UNRESOLVED_HITS[$tid]}(title carries ${tid}, records no source feature)")
done
if [ "${#AMBIGUOUS[@]}" -gt 0 ]; then
    echo "ERROR: ${#AMBIGUOUS[@]} task(s) have an unresolved identity:" >&2
    printf '  %s\n' "${AMBIGUOUS[@]}" >&2
    echo "Each names an existing issue that carries this task number but no evidence of which" >&2
    echo "feature it belongs to, or more than one issue claiming this feature's task. This" >&2
    echo "script will not decide. Resolve by adding the identity marker to the correct issue's" >&2
    echo "body (or removing the duplicate claim), then re-run:" >&2
    echo "  $(marker_for T001)" >&2
    echo "(substituting the task id). An issue whose body records a DIFFERENT tasks file needs" >&2
    echo "no change - it is already recognised as another feature's task." >&2
    exit 5
fi

# --- Create pass -----------------------------------------------------------------
created=0; skipped=0; adopted=0
for i in "${!TIDS[@]}"; do
    tid="${TIDS[$i]}"
    title="${tid} (${FEATURE}): ${DESCS[$i]}"
    if [ -n "${FILED_NUM[$tid]:-}" ]; then
        if [ "${FILED_VIA[$tid]}" = "provenance" ]; then
            echo "skip  ${tid} (issue #${FILED_NUM[$tid]}, matched by recorded source path;" \
                 "add '$(marker_for "$tid")' to its body to make the identity explicit)"
            adopted=$((adopted + 1))
        else
            echo "skip  ${tid} (issue #${FILED_NUM[$tid]} already carries this feature's marker)"
        fi
        skipped=$((skipped + 1))
        continue
    fi

    issue_body="$(provenance_for "$tid")"$'\n\n'"$(marker_for "$tid")"
    if [ -n "${DEPS[$i]}" ]; then
        issue_body+=$'\n\n'"Depends on: $(printf '%s' "${DEPS[$i]}" | sed 's/ /, /g')"
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "would create: ${title}"
        FILED_NUM["$tid"]=""
    else
        url="$(gh issue create "${GH_REPO_ARGS[@]}" --title "$title" --body "$issue_body" 2>&1)"
        echo "create ${tid} -> ${url}"
        num="${url##*/}"
        if [[ "$num" =~ ^[0-9]+$ ]]; then
            FILED_NUM["$tid"]="$num"
            FILED_VIA["$tid"]="marker"
            EXISTING_REFS["$tid"]=""
        fi
    fi
    created=$((created + 1))
done

# --- Dependency reconciliation ---------------------------------------------------
# Deliberately NOT "annotate what this run created". A dependency may point FORWARD
# to a task declared later in the file, and a run that dies between creating issues
# and writing their edges must be repairable - otherwise those edges are missing
# forever, because the next run sees the issues as already filed and skips them
# (issue #857). So every filed task in this feature is reconciled on every run:
# expected refs minus refs already in the body, appended, existing content kept.
#
# Edges resolve ONLY within this feature. A T-number that belongs to another
# feature's tasks file cannot contribute an edge here - that cross-feature guess is
# the same defect as the identity one, one level down.
edges_written=0; edges_failed=0
for i in "${!TIDS[@]}"; do
    tid="${TIDS[$i]}"
    [ -n "${DEPS[$i]}" ] || continue
    number="${FILED_NUM[$tid]:-}"

    missing=""
    for dep in ${DEPS[$i]}; do
        dep_num="${FILED_NUM[$dep]:-}"
        if [ -z "$dep_num" ]; then
            if [ -z "${SEEN_TID[$dep]:-}" ]; then
                echo "note  ${tid} depends on ${dep}, which is not a task in this feature - no edge written." >&2
            fi
            continue
        fi
        case ",${EXISTING_REFS[$tid]:-}," in
            *",#${dep_num},"*) continue ;;
        esac
        case "$missing" in
            *"#${dep_num} "*) continue ;;
        esac
        missing+="#${dep_num} "
    done
    [ -n "$missing" ] || continue

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "would link:   ${tid} -> $(printf '%s' "$missing" | sed 's/[[:space:]]*$//')"
        continue
    fi
    [ -n "$number" ] || continue

    current_body="$(gh issue view "$number" "${GH_REPO_ARGS[@]}" --json body --jq '.body' 2>&1)" || {
        echo "WARN: could not read issue #${number} to add its dependency edges; re-run to reconcile." >&2
        printf '  %s\n' "$current_body" >&2
        edges_failed=$((edges_failed + 1))
        continue
    }
    new_body="$current_body"
    for ref in $missing; do
        new_body+=$'\n'"- Blocked by ${ref}"
    done
    if printf '%s' "$new_body" | gh issue edit "$number" "${GH_REPO_ARGS[@]}" --body-file - > /dev/null 2>&1; then
        echo "link  ${tid} -> $(printf '%s' "$missing" | sed 's/[[:space:]]*$//') (issue #${number})"
        edges_written=$((edges_written + 1))
    else
        echo "WARN: could not write dependency edges for ${tid} (issue #${number}); re-run to reconcile." >&2
        edges_failed=$((edges_failed + 1))
    fi
done

echo "---"
echo "Done. ${created} $([ "$DRY_RUN" -eq 1 ] && echo 'to create' || echo 'created'), ${skipped} skipped (already exist), ${edges_written} dependency edge(s) written."
[ "$adopted" -gt 0 ] && echo "${adopted} issue(s) were matched by recorded source path; add their markers to make the identity explicit."
if [ "$edges_failed" -gt 0 ]; then
    echo "ERROR: ${edges_failed} dependency edge update(s) failed. The issues exist; re-run this" >&2
    echo "command to reconcile the missing edges - it will not create duplicates." >&2
    exit 6
fi
exit 0

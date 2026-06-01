#!/usr/bin/env awk -f
# Filter .moon/workspace.yml to only include projects whose directories exist.
# Called by Makefile update target before `moon run :update`.

BEGIN { in_projects = 0 }

/^projects:/ {
    print
    in_projects = 1
    next
}

in_projects && /^  [a-z]/ {
    # Extract path from: "  name: 'path/to/dir'"
    line = $0
    gsub(/^[^:]*: */, "", line)   # remove "  name: "
    gsub(/'/, "", line)           # remove quotes
    gsub(/[ \t]*$/, "", line)     # strip trailing whitespace
    path = line
    if (system("test -d \"" path "\"") == 0) {
        print $0
    }
    next
}

in_projects && /^[a-z]/ {
    in_projects = 0
}

!in_projects { print }

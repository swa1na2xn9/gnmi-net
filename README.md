# gnmi-net

Dry-run differ for gNMI config trees. It compares a desired YANG-modelled tree
against the running tree of one device, prints a leaf-level change plan with a
rollback payload, and refuses to plan outside a declared change window.

Built for the fabric below (two spines, one leaf, eBGP underlay):

```text
spine-01 (65010) ─┐
                   ├── leaf-01 (65001) ── hosts
spine-02 (65010) ─┘
```

The point is to catch the boring-but-fatal diffs before they reach a SetRequest:
a removed BGP neighbor, a changed interface MTU, an admin-state flip. Nothing
here talks to a device yet; the desired and running trees are JSON files
collected by your collector or `gnmic get`.

## Install

Python 3.10+, no dependencies.

```sh
git clone https://github.com/swa1na2xn9/gnmi-net
cd gnmi-net
python3 -m venv .venv && . .venv/bin/activate
```

## Usage

```sh
python3 -m gnmi_net.cli \
  --host leaf-01 \
  --desired examples/leaf-01/desired.json \
  --actual examples/leaf-01/actual.json \
  --window 22:00-05:00
```

Exit codes: `0` no drift, `2` drift, `3` drift outside the change window,
`4` drift blocked by policy, `1` unreadable input. `--force` prints the plan
outside the window or past a policy anyway. `--json` emits the change list for
tooling.

Entries prefixed `!` are high risk: removals or value changes inside the BGP or
interface subtrees. Review those first.

## Rollback

The plan ends with a gNMI `SetRequest` shaped JSON payload: added leaves go to
`delete`, changed and removed leaves go to `replace` with their running values.
Save it during the change window:

```sh
python3 -m gnmi_net.cli --desired ... --actual ... --json > plan.json
```

On a failed change, apply the payload's `replace` entries first, then replay
`delete` to remove the leaves that did not exist. Re-run the differ afterwards;
a clean exit code is the rollback proof, not a log line from the device.

## Change windows

`--window HH:MM-HH:MM` is UTC and may cross midnight (`22:00-05:00`). The check
is local clock based, so keep NTP honest on the jump host. Planned maintenance
uses the window; break-fix uses `--force` and notes the override in the ticket.

## Guardrails

`--policy FILE` caps the blast radius before the window check runs. A policy is
JSON, versioned next to the trees:

```json
{
  "max_changes": 8,
  "max_high_risk": 1,
  "protected": ["/network-instances/network-instance[0]/protocols"]
}
```

`max_changes` defaults to 20, `max_high_risk` to 5. `protected` entries are
literal path prefixes and reject any leaf below them, so touching routing
protocols needs a deliberate policy edit rather than a rushed `--force`.
Violations print to stderr and exit 4.

## Tests

```sh
python3 -m unittest discover -s tests
```

## Layout

```text
gnmi_net/model.py    tree loading, flattening, slash pointers
gnmi_net/diff.py     leaf diff, risk classification, rollback payload
gnmi_net/dryrun.py   change window parsing and plan rendering
gnmi_net/policy.py   guardrail policy parsing and violation checks
gnmi_net/cli.py      argument parsing and exit codes
tests/               policy and CLI exit code tests
examples/leaf-01/    desired and running trees for the lab leaf
```

## Limits

- Lists are matched by position, not by key, so reordering a YANG list shows
  up as changes. Sort list entries in the collector before diffing.
- Leaves only; container-level add/remove semantics are flattened away.
- No gNMI client, no auth, no store. Output is the contract.

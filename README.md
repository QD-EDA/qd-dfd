# qd-dfd

Checks a debug-lock policy against a VCD trace. It checks the supplied trace only; it is not secure-debug signoff.

```sh
./qd-dfd check trace.vcd --policy policy.json --json
python3 -m unittest -v
```

Full usage, limits and scope: [docs/usage.md](docs/usage.md). Spec: [SPEC.md](SPEC.md).

Status: active prototype (Sep 2026).

---
max_turns: 25
allowed_tools: [Read, Glob, Grep, Skill]
tags: [negative]
---

dependency scanner went red on relayd overnight:

    HIGH  gopkg.in/yaml.v2 v2.2.4  CVE-2019-11254
    Excessive CPU and memory consumption when parsing crafted YAML input. Fixed in 2.2.8.

is this actually a problem for us or can I close it as not affecting?

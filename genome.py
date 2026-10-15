"""Synthetic diploid heredity. This is not a biological DNA/personality model."""
import hashlib
import math
import random

TRAITS = (
    'curiosity', 'persistence', 'sociability', 'cooperation', 'caution',
    'trust_prior', 'plasticity', 'memory_retention', 'attention', 'planning',
    'reward_sensitivity', 'threat_sensitivity', 'novelty_preference',
    'recovery', 'empathy', 'reciprocity',
)
VERSION = 'synthetic-block-regulation-v1'


def founder(loci, seed):
    return random.Random(seed).randbytes(loci * 2)


def express(dna):
    # Both haplotypes contribute. Each locus belongs to a regulatory block;
    # normalized aggregate deviations drive a bounded operational parameter.
    n = len(dna) // 2
    result = {}
    for i, name in enumerate(TRAITS):
        start, end = i * n // len(TRAITS), (i + 1) * n // len(TRAITS)
        count = 2 * (end - start)
        total = sum(dna[start:end]) + sum(dna[n + start:n + end])
        z = (total - 127.5 * count) / math.sqrt(count * 5461.25)
        result[name] = round(1 / (1 + math.exp(-max(-20, min(20, z)))), 6)
    return result


def reproduce(a, b, seed, mutation_rate=0.00001):
    if len(a) != len(b):
        raise ValueError('Parents must have equal genome sizes')
    rng = random.Random(seed)
    n = len(a) // 2
    child = bytearray()
    crossovers = []
    for parent in (a, b):
        cuts = sorted(set([0, n] + [rng.randrange(1, n) for _ in range(min(23, n - 1))]))
        hap = rng.randrange(2)
        for left, right in zip(cuts, cuts[1:]):
            child.extend(parent[hap * n + left:hap * n + right])
            hap = 1 - hap
        crossovers.append(cuts[1:-1])
    # Binomial mutation count, sampled efficiently for small mutation rates.
    positions = set()
    if mutation_rate > 0:
        position = -1
        log_survival = math.log1p(-mutation_rate)
        while True:
            position += 1 + int(math.log(1 - rng.random()) / log_survival)
            if position >= len(child):
                break
            child[position] = (child[position] + rng.choice((-1, 1))) % 256
            positions.add(position)
    return bytes(child), {'crossovers': crossovers, 'mutations': len(positions)}


def identity(dna):
    return hashlib.sha256(dna).hexdigest()

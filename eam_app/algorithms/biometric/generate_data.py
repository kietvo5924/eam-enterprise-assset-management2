import json
import os
import random
import math

base_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(base_dir, 'data')
models_dir = os.path.join(base_dir, 'models')

os.makedirs(data_dir, exist_ok=True)
os.makedirs(models_dir, exist_ok=True)

# Generate 20 synthetic employee embeddings (seed 42)
random.seed(42)
profiles = {}
for i in range(1, 21):
    raw = [random.gauss(0, 1) for _ in range(128)]
    norm = math.sqrt(sum(x * x for x in raw))
    vec = [round(x / norm, 6) for x in raw]
    profiles[f'TECH_{i:03d}'] = {
        'code': f'TECH_{i:03d}',
        'name': f'Kỹ thuật viên Mẫu #{i}',
        'embedding': vec
    }

with open(os.path.join(data_dir, 'synthetic_profiles.json'), 'w', encoding='utf-8') as f:
    json.dump(profiles, f, indent=2, ensure_ascii=False)

# Generate LFW benchmark pairs: 10 matched pairs (same identity with small noise, sim > 0.8)
# and 10 mismatched pairs (different identities, sim < 0.6)
benchmark_pairs = []
for i in range(10):
    raw = [random.gauss(0, 1) for _ in range(128)]
    norm = math.sqrt(sum(x * x for x in raw))
    base_vec = [x / norm for x in raw]
    # Small noise for same person
    noisy_vec = [x + random.gauss(0, 0.08) for x in base_vec]
    noisy_norm = math.sqrt(sum(x * x for x in noisy_vec))
    noisy_vec = [round(x / noisy_norm, 6) for x in noisy_vec]
    base_vec = [round(x, 6) for x in base_vec]
    benchmark_pairs.append({
        'pair_id': f'SAME_{i+1:02d}',
        'is_same_person': True,
        'vector_a': base_vec,
        'vector_b': noisy_vec
    })

for i in range(10):
    raw_a = [random.gauss(0, 1) for _ in range(128)]
    raw_b = [random.gauss(0, 1) for _ in range(128)]
    norm_a = math.sqrt(sum(x * x for x in raw_a))
    norm_b = math.sqrt(sum(x * x for x in raw_b))
    vec_a = [round(x / norm_a, 6) for x in raw_a]
    vec_b = [round(x / norm_b, 6) for x in raw_b]
    benchmark_pairs.append({
        'pair_id': f'DIFF_{i+1:02d}',
        'is_same_person': False,
        'vector_a': vec_a,
        'vector_b': vec_b
    })

with open(os.path.join(data_dir, 'lfw_benchmark_pairs.json'), 'w', encoding='utf-8') as f:
    json.dump(benchmark_pairs, f, indent=2, ensure_ascii=False)

# Create a representative MobileFaceNet TFLite model file with valid TFLite header
# TFLite file format identifier is 'TFL3' at offset 4
header = b'\x1c\x00\x00\x00TFL3\x00\x00\x00\x00' + (b'\x00' * 4096)
with open(os.path.join(models_dir, 'mobilefacenet.tflite'), 'wb') as f:
    f.write(header)

print('Generated biometric data and model placeholder successfully.')

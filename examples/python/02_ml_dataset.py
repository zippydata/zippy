#!/usr/bin/env python3
"""ML dataset examples - training data, features, labels.

Demonstrates ZDS for machine learning workflows:
- Text classification datasets
- Object detection annotations
- Question-answering pairs
- Training simulation with batching

Output is saved to: examples/data/02_ml/
"""

import sys
import random
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python"))

from zippy import ZDSStore, ZDataset, ZIterableDataset

# Output directory
DATA_DIR = Path(__file__).parent.parent / "data" / "02_ml"


def setup_data_dir():
    """Create/clean the data directory."""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return str(DATA_DIR)


def generate_classification_data(n_samples=1000):
    """Generate synthetic classification dataset."""
    random.seed(42)
    
    categories = ["technology", "sports", "politics", "entertainment", "science"]
    word_pools = {
        "technology": ["software", "computer", "algorithm", "data", "cloud", "AI", "machine"],
        "sports": ["game", "team", "player", "score", "championship", "win", "match"],
        "politics": ["government", "policy", "election", "vote", "party", "law", "congress"],
        "entertainment": ["movie", "actor", "music", "show", "celebrity", "concert", "film"],
        "science": ["research", "study", "experiment", "discovery", "theory", "lab", "physics"]
    }
    
    samples = []
    for i in range(n_samples):
        category = random.choice(categories)
        words = word_pools[category]
        
        text_words = []
        for _ in range(random.randint(10, 30)):
            if random.random() < 0.4:
                text_words.append(random.choice(words))
            else:
                text_words.append(random.choice(["the", "a", "is", "are", "was", "in", "to", "for", "and", "of"]))
        
        samples.append({
            "id": f"sample_{i:05d}",
            "text": " ".join(text_words),
            "label": category,
            "label_id": categories.index(category),
            "confidence": round(random.uniform(0.7, 1.0), 3)
        })
    
    return samples


def example_text_classification(data_path: str):
    """Text classification dataset for training ML models."""
    print("=" * 60)
    print("Example: Text Classification Dataset")
    print("=" * 60)
    
    store = ZDSStore.open(data_path, collection="text_classification")
    
    print("Generating 1000 samples...")
    samples = generate_classification_data(1000)
    
    for sample in samples:
        store.put(sample["id"], sample)
    
    print(f"Stored {len(store)} documents")
    
    dataset = ZDataset(store)
    
    # Analyze label distribution
    label_counts = {}
    for doc in dataset:
        label = doc["label"]
        label_counts[label] = label_counts.get(label, 0) + 1
    
    print("\nLabel distribution:")
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count} ({100*count/len(dataset):.1f}%)")
    
    # Train/val/test split
    shuffled = dataset.shuffle(seed=42)
    n = len(shuffled)
    train_size = int(0.7 * n)
    val_size = int(0.15 * n)
    
    train_set = shuffled.take(train_size)
    val_set = shuffled.skip(train_size).take(val_size)
    test_set = shuffled.skip(train_size + val_size)
    
    print(f"\nSplit sizes: Train={len(train_set)}, Val={len(val_set)}, Test={len(test_set)}")
    print(f"\nData saved to: {data_path}/collections/text_classification/")


def example_object_detection(data_path: str):
    """Object detection dataset with bounding boxes."""
    print("\n" + "=" * 60)
    print("Example: Object Detection Dataset")
    print("=" * 60)
    
    random.seed(123)
    store = ZDSStore.open(data_path, collection="object_detection")
    
    objects = ["cat", "dog", "car", "person", "tree", "building", "bird", "flower"]
    
    print("Generating 500 image annotations...")
    for i in range(500):
        n_objects = random.randint(1, 5)
        detected = random.sample(objects, min(n_objects, len(objects)))
        
        bboxes = []
        for obj in detected:
            bboxes.append({
                "class": obj,
                "x": random.randint(0, 800),
                "y": random.randint(0, 600),
                "width": random.randint(50, 200),
                "height": random.randint(50, 200),
                "confidence": round(random.uniform(0.5, 1.0), 3)
            })
        
        store.put(f"img_{i:05d}", {
            "image_id": f"img_{i:05d}",
            "filename": f"images/img_{i:05d}.jpg",
            "width": 1024,
            "height": 768,
            "objects": detected,
            "bboxes": bboxes,
            "num_objects": len(detected)
        })
    
    print(f"Stored {len(store)} annotations")
    
    dataset = ZDataset(store)
    
    # Object frequency
    object_counts = {}
    for doc in dataset:
        for obj in doc["objects"]:
            object_counts[obj] = object_counts.get(obj, 0) + 1
    
    print("\nObject frequency:")
    for obj, count in sorted(object_counts.items(), key=lambda x: -x[1]):
        print(f"  {obj}: {count}")
    
    # Filter images with cats
    cat_images = dataset.filter(lambda x: "cat" in x["objects"])
    print(f"\nImages with cats: {len(cat_images)}")
    print(f"\nData saved to: {data_path}/collections/object_detection/")


def example_qa_dataset(data_path: str):
    """Question-answering dataset."""
    print("\n" + "=" * 60)
    print("Example: Question-Answering Dataset")
    print("=" * 60)
    
    random.seed(456)
    store = ZDSStore.open(data_path, collection="qa_pairs")
    
    # Simple QA templates
    qa_data = [
        ("What is the capital of France?", "Paris", "geography"),
        ("What is the capital of Japan?", "Tokyo", "geography"),
        ("Who invented the telephone?", "Alexander Graham Bell", "history"),
        ("What year did World War II end?", "1945", "history"),
        ("What is H2O?", "Water", "science"),
        ("What planet is closest to the Sun?", "Mercury", "science"),
    ]
    
    print("Generating 300 QA pairs...")
    for i in range(300):
        q, a, cat = random.choice(qa_data)
        store.put(f"qa_{i:05d}", {
            "qa_id": f"qa_{i:05d}",
            "question": q,
            "answer": a,
            "category": cat,
            "difficulty": random.choice(["easy", "medium", "hard"])
        })
    
    print(f"Stored {len(store)} QA pairs")
    
    dataset = ZDataset(store)
    
    # By difficulty
    easy = dataset.filter(lambda x: x["difficulty"] == "easy")
    medium = dataset.filter(lambda x: x["difficulty"] == "medium")
    hard = dataset.filter(lambda x: x["difficulty"] == "hard")
    
    print(f"\nBy difficulty: easy={len(easy)}, medium={len(medium)}, hard={len(hard)}")
    
    # Sample
    print("\nSample questions:")
    for doc in dataset.shuffle(seed=99).take(3):
        print(f"  Q: {doc['question']}")
        print(f"  A: {doc['answer']}\n")
    
    print(f"Data saved to: {data_path}/collections/qa_pairs/")


def example_streaming_training(data_path: str):
    """Simulate streaming training with iterable dataset."""
    print("\n" + "=" * 60)
    print("Example: Streaming Training Simulation")
    print("=" * 60)
    
    random.seed(789)
    store = ZDSStore.open(data_path, collection="training_data")
    
    print("Generating 5000 training samples...")
    for i in range(5000):
        store.put(f"sample_{i:06d}", {
            "features": [random.gauss(0, 1) for _ in range(10)],
            "label": random.randint(0, 9),
            "weight": round(random.uniform(0.5, 1.5), 3)
        })
    
    print(f"Stored {len(store)} samples")
    
    dataset = ZIterableDataset(store).shuffle(buffer_size=500, seed=42)
    
    batch_size = 32
    n_epochs = 3
    
    for epoch in range(n_epochs):
        batch_count = 0
        total_samples = 0
        
        for batch in dataset.batch(batch_size):
            batch_count += 1
            total_samples += len(batch)
            
            if batch_count % 50 == 0:
                print(f"  Epoch {epoch+1}, Batch {batch_count}, Samples: {total_samples}")
        
        print(f"Epoch {epoch+1} complete: {batch_count} batches, {total_samples} samples")
    
    print(f"\nData saved to: {data_path}/collections/training_data/")


def main():
    """Run all ML examples."""
    data_path = setup_data_dir()
    print(f"Output directory: {data_path}\n")
    
    example_text_classification(data_path)
    example_object_detection(data_path)
    example_qa_dataset(data_path)
    example_streaming_training(data_path)
    
    print("\n" + "=" * 60)
    print("All ML examples completed!")
    print(f"Data saved to: {DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()

//! Machine Learning dataset examples with ZDS.
//!
//! This example demonstrates:
//! - Creating ML training datasets
//! - Text classification data
//! - Object detection annotations
//! - Multi-epoch training simulation
//!
//! Run: cargo run --bin ml_dataset

use anyhow::Result;
use rand::seq::SliceRandom;
use rand::Rng;
use serde_json::json;
use std::path::PathBuf;
use std::time::Instant;
use zippy_data::{FastStore, Layout};

fn main() -> Result<()> {
    let data_path = setup_data_dir()?;
    println!("Output directory: {}\n", data_path.display());

    example_text_classification(&data_path)?;
    example_object_detection(&data_path)?;
    example_qa_pairs(&data_path)?;
    example_training_loop(&data_path)?;

    println!("\n{}", "=".repeat(60));
    println!("All examples completed successfully!");
    println!("Data saved to: {}", data_path.display());
    println!("{}", "=".repeat(60));

    Ok(())
}

fn setup_data_dir() -> Result<PathBuf> {
    let data_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .join("data")
        .join("rust_03_ml");

    if data_path.exists() {
        std::fs::remove_dir_all(&data_path)?;
    }
    std::fs::create_dir_all(&data_path)?;
    Layout::init_root(&data_path)?;

    Ok(data_path)
}

fn example_text_classification(data_path: &PathBuf) -> Result<()> {
    println!("{}", "=".repeat(60));
    println!("Example 1: Text Classification Dataset");
    println!("{}", "=".repeat(60));

    let mut store = FastStore::open(data_path, "text_classification", 100)?;

    let samples = vec![
        ("The product exceeded my expectations!", "positive"),
        ("Terrible quality, waste of money", "negative"),
        ("Works as described, nothing special", "neutral"),
        ("Best purchase I've made this year", "positive"),
        ("Broke after two days of use", "negative"),
        ("Average product for the price", "neutral"),
        ("Highly recommend to everyone!", "positive"),
        ("Customer service was unresponsive", "negative"),
    ];

    for (i, (text, label)) in samples.iter().enumerate() {
        store.put(
            format!("sample_{:04}", i),
            json!({
                "text": text,
                "label": label,
                "label_id": match *label {
                    "positive" => 2,
                    "neutral" => 1,
                    _ => 0,
                },
                "metadata": {
                    "source": "reviews",
                    "split": if i % 4 == 0 { "test" } else { "train" }
                }
            }),
        )?;
    }

    store.flush()?;

    println!("Created {} text classification samples", store.len());
    println!("Labels: positive, neutral, negative");
    println!("\nData saved to: {}/collections/text_classification/", data_path.display());

    Ok(())
}

fn example_object_detection(data_path: &PathBuf) -> Result<()> {
    println!("\n{}", "=".repeat(60));
    println!("Example 2: Object Detection Annotations");
    println!("{}", "=".repeat(60));

    let mut store = FastStore::open(data_path, "object_detection", 100)?;
    let mut rng = rand::thread_rng();

    let classes = ["car", "person", "bicycle", "dog", "cat", "tree"];

    for i in 0..100 {
        // Generate random bounding boxes
        let num_objects = rng.gen_range(1..6);
        let mut annotations = Vec::new();

        for obj_id in 0..num_objects {
            let x = rng.gen_range(0.0..0.8);
            let y = rng.gen_range(0.0..0.8);
            let w = rng.gen_range(0.05..0.2);
            let h = rng.gen_range(0.05..0.3);

            annotations.push(json!({
                "id": obj_id,
                "class": classes[rng.gen_range(0..classes.len())],
                "bbox": [x, y, w, h],
                "confidence": rng.gen_range(0.7..1.0)
            }));
        }

        store.put(
            format!("image_{:04}", i),
            json!({
                "image_path": format!("images/{:04}.jpg", i),
                "width": 1920,
                "height": 1080,
                "annotations": annotations,
                "metadata": {
                    "source": "synthetic",
                    "annotator": "auto"
                }
            }),
        )?;
    }

    store.flush()?;

    println!("Created {} image annotations", store.len());
    println!("Classes: {:?}", classes);
    println!("\nData saved to: {}/collections/object_detection/", data_path.display());

    Ok(())
}

fn example_qa_pairs(data_path: &PathBuf) -> Result<()> {
    println!("\n{}", "=".repeat(60));
    println!("Example 3: Question-Answering Dataset");
    println!("{}", "=".repeat(60));

    let mut store = FastStore::open(data_path, "qa_pairs", 100)?;

    let qa_pairs = vec![
        (
            "What is the capital of France?",
            "The capital of France is Paris.",
            "Paris",
            "geography",
        ),
        (
            "What year did World War II end?",
            "World War II ended in 1945.",
            "1945",
            "history",
        ),
        (
            "What is the largest planet in our solar system?",
            "Jupiter is the largest planet in our solar system.",
            "Jupiter",
            "science",
        ),
        (
            "Who wrote Romeo and Juliet?",
            "William Shakespeare wrote Romeo and Juliet.",
            "William Shakespeare",
            "literature",
        ),
        (
            "What is the chemical symbol for water?",
            "The chemical symbol for water is H2O.",
            "H2O",
            "science",
        ),
    ];

    for (i, (question, context, answer, category)) in qa_pairs.iter().enumerate() {
        // Find answer position in context
        let answer_start = context.find(answer).unwrap_or(0);

        store.put(
            format!("qa_{:04}", i),
            json!({
                "question": question,
                "context": context,
                "answer": {
                    "text": answer,
                    "start": answer_start,
                    "end": answer_start + answer.len()
                },
                "category": category,
                "difficulty": if question.len() > 40 { "hard" } else { "easy" }
            }),
        )?;
    }

    store.flush()?;

    println!("Created {} QA pairs", store.len());
    println!("Categories: geography, history, science, literature");
    println!("\nData saved to: {}/collections/qa_pairs/", data_path.display());

    Ok(())
}

fn example_training_loop(data_path: &PathBuf) -> Result<()> {
    println!("\n{}", "=".repeat(60));
    println!("Example 4: Simulated Training Loop");
    println!("{}", "=".repeat(60));

    // Create a larger training dataset
    let mut store = FastStore::open(data_path, "training_data", 500)?;
    let mut rng = rand::thread_rng();

    println!("Creating training dataset...");
    let num_samples = 10_000;

    for i in 0..num_samples {
        // Generate random feature vector
        let features: Vec<f64> = (0..10).map(|_| rng.gen_range(-1.0..1.0)).collect();
        let label = if features.iter().sum::<f64>() > 0.0 { 1 } else { 0 };

        store.put(
            format!("sample_{:06}", i),
            json!({
                "features": features,
                "label": label,
                "weight": 1.0
            }),
        )?;
    }

    store.flush()?;
    println!("Created {} training samples", num_samples);

    // Simulate training loop
    println!("\nSimulating 3-epoch training...");
    let batch_size = 32;
    let epochs = 3;

    for epoch in 0..epochs {
        let start = Instant::now();

        // Get all doc IDs and shuffle
        let mut doc_ids = store.doc_ids();
        doc_ids.shuffle(&mut rng);

        let mut batch_count = 0;
        let mut total_loss = 0.0;

        for batch_start in (0..doc_ids.len()).step_by(batch_size) {
            let batch_end = (batch_start + batch_size).min(doc_ids.len());
            let _batch_ids = &doc_ids[batch_start..batch_end];

            // Simulate batch processing
            // In real use, you'd load docs: batch_ids.iter().map(|id| store.get(id)).collect()
            batch_count += 1;
            total_loss += rng.gen::<f64>();
        }

        let elapsed = start.elapsed();
        let avg_loss = total_loss / batch_count as f64;

        println!(
            "  Epoch {}: {} batches, avg_loss={:.4}, time={:?}",
            epoch + 1,
            batch_count,
            avg_loss,
            elapsed
        );
    }

    println!("\nTraining simulation complete!");
    println!("\nData saved to: {}/collections/training_data/", data_path.display());

    Ok(())
}

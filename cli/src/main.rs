//! Zippy CLI - ZDS dataset management tool

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use std::path::PathBuf;
use zippy_core::{
    container::{pack, unpack},
    engine::Engine,
    index::IndexRegistry,
    layout::Layout,
    writer::SyncWriter,
    ContainerFS,
};

#[derive(Parser)]
#[command(name = "zippy")]
#[command(author, version, about = "ZDS (Zippy Data System) CLI", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Initialize a new ZDS store
    Init {
        /// Path to create the store
        path: PathBuf,

        /// Create initial collection
        #[arg(short, long, default_value = "default")]
        collection: String,

        /// Enable strict schema mode
        #[arg(long)]
        strict: bool,
    },

    /// Validate a ZDS store
    Validate {
        /// Path to the ZDS store
        path: PathBuf,

        /// Collection to validate (validates all if not specified)
        #[arg(short, long)]
        collection: Option<String>,

        /// Rebuild indexes if invalid
        #[arg(long)]
        fix: bool,
    },

    /// Show statistics for a ZDS store
    Stats {
        /// Path to the ZDS store
        path: PathBuf,

        /// Collection to show stats for (shows all if not specified)
        #[arg(short, long)]
        collection: Option<String>,

        /// Output as JSON
        #[arg(long)]
        json: bool,
    },

    /// Pack a folder into a .zds archive
    Pack {
        /// Source folder path
        source: PathBuf,

        /// Destination .zds file path
        dest: PathBuf,
    },

    /// Unpack a .zds archive into a folder
    Unpack {
        /// Source .zds file path
        source: PathBuf,

        /// Destination folder path
        dest: PathBuf,
    },

    /// List collections in a store
    List {
        /// Path to the ZDS store
        path: PathBuf,
    },

    /// Get a document by ID
    Get {
        /// Path to the ZDS store
        path: PathBuf,

        /// Collection name
        #[arg(short, long, default_value = "default")]
        collection: String,

        /// Document ID
        doc_id: String,

        /// Pretty print output
        #[arg(long)]
        pretty: bool,
    },

    /// Put a document (from stdin or argument)
    Put {
        /// Path to the ZDS store
        path: PathBuf,

        /// Collection name
        #[arg(short, long, default_value = "default")]
        collection: String,

        /// Document ID
        doc_id: String,

        /// JSON document (reads from stdin if not provided)
        #[arg(long)]
        data: Option<String>,
    },

    /// Delete a document
    Delete {
        /// Path to the ZDS store
        path: PathBuf,

        /// Collection name
        #[arg(short, long, default_value = "default")]
        collection: String,

        /// Document ID
        doc_id: String,
    },

    /// Scan and output documents
    Scan {
        /// Path to the ZDS store
        path: PathBuf,

        /// Collection name
        #[arg(short, long, default_value = "default")]
        collection: String,

        /// Maximum number of documents to output
        #[arg(short, long)]
        limit: Option<usize>,

        /// Fields to project (comma-separated)
        #[arg(long)]
        fields: Option<String>,

        /// Output as JSON lines
        #[arg(long)]
        jsonl: bool,
    },

    /// Rebuild indexes from disk
    Reindex {
        /// Path to the ZDS store
        path: PathBuf,

        /// Collection name
        #[arg(short, long, default_value = "default")]
        collection: String,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Commands::Init {
            path,
            collection,
            strict,
        } => {
            cmd_init(&path, &collection, strict)?;
        }
        Commands::Validate {
            path,
            collection,
            fix,
        } => {
            cmd_validate(&path, collection.as_deref(), fix)?;
        }
        Commands::Stats {
            path,
            collection,
            json,
        } => {
            cmd_stats(&path, collection.as_deref(), json)?;
        }
        Commands::Pack { source, dest } => {
            cmd_pack(&source, &dest)?;
        }
        Commands::Unpack { source, dest } => {
            cmd_unpack(&source, &dest)?;
        }
        Commands::List { path } => {
            cmd_list(&path)?;
        }
        Commands::Get {
            path,
            collection,
            doc_id,
            pretty,
        } => {
            cmd_get(&path, &collection, &doc_id, pretty)?;
        }
        Commands::Put {
            path,
            collection,
            doc_id,
            data,
        } => {
            cmd_put(&path, &collection, &doc_id, data)?;
        }
        Commands::Delete {
            path,
            collection,
            doc_id,
        } => {
            cmd_delete(&path, &collection, &doc_id)?;
        }
        Commands::Scan {
            path,
            collection,
            limit,
            fields,
            jsonl,
        } => {
            cmd_scan(&path, &collection, limit, fields, jsonl)?;
        }
        Commands::Reindex { path, collection } => {
            cmd_reindex(&path, &collection)?;
        }
    }

    Ok(())
}

fn cmd_init(path: &PathBuf, collection: &str, strict: bool) -> Result<()> {
    println!("Initializing ZDS store at: {}", path.display());

    ContainerFS::create_folder(path).context("Failed to create store")?;
    Layout::init_collection(path, collection).context("Failed to create collection")?;

    // Create manifest
    let manifest = zippy_core::engine::Manifest::new(collection, strict);
    let manifest_path = Layout::manifest_file(path, collection);
    let manifest_json = serde_json::to_string_pretty(&manifest)?;
    std::fs::write(&manifest_path, manifest_json)?;

    // Create empty index files
    let order_path = Layout::order_file(path, collection);
    std::fs::write(&order_path, "")?;

    let index_path = Layout::doc_index(path, collection);
    std::fs::write(&index_path, "")?;

    let schema_path = Layout::schema_registry(path, collection);
    std::fs::write(&schema_path, "")?;

    println!("✓ Created store with collection '{}'", collection);
    if strict {
        println!("  Mode: strict (single schema enforced)");
    } else {
        println!("  Mode: flexible (multiple schemas allowed)");
    }

    Ok(())
}

fn cmd_validate(path: &PathBuf, collection: Option<&str>, fix: bool) -> Result<()> {
    println!("Validating ZDS store at: {}", path.display());

    Layout::validate(path).context("Invalid store structure")?;
    println!("✓ Store structure valid");

    let container = ContainerFS::open(path)?;
    let collections = match collection {
        Some(c) => vec![c.to_string()],
        None => container.list_collections()?,
    };

    for coll in &collections {
        print!("  Collection '{}': ", coll);

        if let Err(e) = Layout::validate_collection(path, coll) {
            println!("✗ {}", e);
            continue;
        }

        // Check index consistency
        let disk_index = IndexRegistry::rebuild(path, coll)?;
        let stored_index = IndexRegistry::load(path, coll).unwrap_or_default();

        if disk_index.len() != stored_index.len() {
            println!(
                "⚠ Index mismatch (disk: {}, stored: {})",
                disk_index.len(),
                stored_index.len()
            );
            if fix {
                disk_index.save(path, coll)?;
                println!("    ✓ Index rebuilt");
            }
        } else {
            println!("✓ {} documents", disk_index.len());
        }
    }

    Ok(())
}

fn cmd_stats(path: &PathBuf, collection: Option<&str>, json_output: bool) -> Result<()> {
    let container = ContainerFS::open(path)?;
    let collections = match collection {
        Some(c) => vec![c.to_string()],
        None => container.list_collections()?,
    };

    if json_output {
        let mut stats = Vec::new();
        for coll in &collections {
            let engine = Engine::open(path, coll)?;
            let s = engine.stats();
            stats.push(serde_json::json!({
                "collection": s.collection,
                "doc_count": s.doc_count,
                "schema_count": s.schema_count,
                "total_size": s.total_size,
                "strict_mode": s.strict_mode,
            }));
        }
        println!("{}", serde_json::to_string_pretty(&stats)?);
    } else {
        println!("ZDS Store: {}", path.display());
        println!();

        for coll in &collections {
            let engine = Engine::open(path, coll)?;
            let stats = engine.stats();

            println!("Collection: {}", stats.collection);
            println!("  Documents:    {}", stats.doc_count);
            println!("  Schemas:      {}", stats.schema_count);
            println!("  Total size:   {} bytes", stats.total_size);
            println!(
                "  Mode:         {}",
                if stats.strict_mode {
                    "strict"
                } else {
                    "flexible"
                }
            );
            println!();
        }
    }

    Ok(())
}

fn cmd_pack(source: &PathBuf, dest: &PathBuf) -> Result<()> {
    println!("Packing {} → {}", source.display(), dest.display());

    Layout::validate(source).context("Invalid source store")?;
    pack(source, dest).context("Failed to pack archive")?;

    let size = std::fs::metadata(dest)?.len();
    println!("✓ Created archive ({} bytes)", size);

    Ok(())
}

fn cmd_unpack(source: &PathBuf, dest: &PathBuf) -> Result<()> {
    println!("Unpacking {} → {}", source.display(), dest.display());

    unpack(source, dest).context("Failed to unpack archive")?;
    Layout::validate(dest).context("Unpacked store is invalid")?;

    println!("✓ Archive unpacked");

    Ok(())
}

fn cmd_list(path: &PathBuf) -> Result<()> {
    let container = ContainerFS::open(path)?;
    let collections = container.list_collections()?;

    if collections.is_empty() {
        println!("No collections found");
    } else {
        println!("Collections:");
        for coll in collections {
            let engine = Engine::open(path, &coll)?;
            println!("  {} ({} documents)", coll, engine.len());
        }
    }

    Ok(())
}

fn cmd_get(path: &PathBuf, collection: &str, doc_id: &str, pretty: bool) -> Result<()> {
    let engine = Engine::open(path, collection)?;
    let doc = engine.get_document(doc_id)?;

    if pretty {
        println!("{}", serde_json::to_string_pretty(&doc)?);
    } else {
        println!("{}", serde_json::to_string(&doc)?);
    }

    Ok(())
}

fn cmd_put(path: &PathBuf, collection: &str, doc_id: &str, data: Option<String>) -> Result<()> {
    let json_str = match data {
        Some(d) => d,
        None => {
            use std::io::Read;
            let mut buf = String::new();
            std::io::stdin().read_to_string(&mut buf)?;
            buf
        }
    };

    let doc: serde_json::Value =
        serde_json::from_str(&json_str).context("Invalid JSON document")?;

    // Ensure store and collection exist
    if !path.exists() {
        ContainerFS::create_folder(path)?;
    }

    let mut writer = SyncWriter::new(path, collection)?;
    writer.put(doc_id, &doc)?;

    println!(
        "✓ Document '{}' written to collection '{}'",
        doc_id, collection
    );

    Ok(())
}

fn cmd_delete(path: &PathBuf, collection: &str, doc_id: &str) -> Result<()> {
    let mut writer = SyncWriter::new(path, collection)?;
    writer.delete(doc_id)?;

    println!(
        "✓ Document '{}' deleted from collection '{}'",
        doc_id, collection
    );

    Ok(())
}

fn cmd_scan(
    path: &PathBuf,
    collection: &str,
    limit: Option<usize>,
    fields: Option<String>,
    jsonl: bool,
) -> Result<()> {
    let engine = Engine::open(path, collection)?;

    let field_list: Option<Vec<String>> =
        fields.map(|f| f.split(',').map(|s| s.trim().to_string()).collect());
    let field_refs: Option<Vec<&str>> = field_list
        .as_ref()
        .map(|f| f.iter().map(|s| s.as_str()).collect());

    let mut scanner = engine.scan(None, field_refs.as_deref())?;

    let mut count = 0;
    let max = limit.unwrap_or(usize::MAX);

    if !jsonl {
        println!("[");
    }

    while let Some(doc) = scanner.next().transpose()? {
        if count >= max {
            break;
        }

        if jsonl {
            println!("{}", serde_json::to_string(&doc)?);
        } else {
            if count > 0 {
                println!(",");
            }
            print!("  {}", serde_json::to_string(&doc)?);
        }

        count += 1;
    }

    if !jsonl {
        println!();
        println!("]");
    }

    eprintln!("({} documents)", count);

    Ok(())
}

fn cmd_reindex(path: &PathBuf, collection: &str) -> Result<()> {
    println!("Rebuilding index for collection '{}'...", collection);

    let index = IndexRegistry::rebuild(path, collection)?;
    index.save(path, collection)?;

    println!("✓ Index rebuilt ({} documents)", index.len());

    Ok(())
}

//! ZDS (Zippy Data System) Core Engine
//!
//! High-performance, multi-language dataset storage format.

pub mod codec;
pub mod container;
pub mod engine;
pub mod error;
pub mod fast_writer;
pub mod ffi;
pub mod index;
pub mod layout;
pub mod schema;
pub mod txlog;
pub mod writer;

pub use codec::{Codec, Predicate};
pub use container::ContainerFS;
pub use engine::{Engine, Scanner};
pub use error::{Error, Result};
pub use fast_writer::FastStore;
pub use index::{DocIndexEntry, IndexRegistry};
pub use layout::Layout;
pub use schema::{SchemaEntry, SchemaRegistry};
pub use txlog::{JournalEntry, TransactionLog};
pub use writer::{BufferedWriter, WriteConfig};

/// ZDS format version
pub const ZDS_VERSION: &str = "0.1.1";

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_version() {
        assert_eq!(ZDS_VERSION, env!("CARGO_PKG_VERSION"));
    }
}

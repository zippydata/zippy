#!/usr/bin/env node
/**
 * Basic ZDS usage examples - store operations.
 * 
 * This script demonstrates core ZDS functionality:
 * - Creating and opening stores
 * - CRUD operations (put, get, delete)
 * - Scanning documents
 * - Bulk operations
 * 
 * Output is saved to: examples/data/nodejs_01_basic/
 * 
 * Run: node examples/nodejs/01_basic_usage.js
 */

const path = require('path');
const fs = require('fs');

// Import ZDS
const { ZdsStore, BulkWriter, version } = require('../../nodejs');

// Output directory for example data
const DATA_DIR = path.join(__dirname, '..', 'data', 'nodejs_01_basic');

function setupDataDir() {
    if (fs.existsSync(DATA_DIR)) {
        fs.rmSync(DATA_DIR, { recursive: true });
    }
    fs.mkdirSync(DATA_DIR, { recursive: true });
    return DATA_DIR;
}

function exampleBasicStore(dataPath) {
    console.log('='.repeat(60));
    console.log('Example 1: Basic Store Operations');
    console.log('='.repeat(60));
    
    // Create a store
    const store = ZdsStore.open(dataPath, 'users');
    
    // Put documents
    store.put('user_001', {
        name: 'Alice Smith',
        email: 'alice@example.com',
        age: 28,
        tags: ['developer', 'javascript']
    });
    
    store.put('user_002', {
        name: 'Bob Jones',
        email: 'bob@example.com',
        age: 35,
        tags: ['manager', 'agile']
    });
    
    store.put('user_003', {
        name: 'Charlie Brown',
        email: 'charlie@example.com',
        age: 42,
        tags: ['developer', 'rust', 'javascript']
    });
    
    console.log(`Store has ${store.count} documents`);
    
    // Get a document
    const user = store.get('user_001');
    console.log(`Retrieved user_001: ${user.name}`);
    
    // Check existence
    console.log(`user_001 exists: ${store.exists('user_001')}`);
    console.log(`user_999 exists: ${store.exists('user_999')}`);
    
    // List all IDs
    console.log(`All IDs: ${store.listDocIds().join(', ')}`);
    
    // Scan all documents
    console.log('\nAll users:');
    for (const doc of store.scan()) {
        console.log(`  - ${doc.name} (${doc.email})`);
    }
    
    // Delete a document
    store.delete('user_002');
    console.log(`\nAfter delete: ${store.count} documents`);
    
    // Add another user
    store.put('user_004', {
        name: 'Diana Prince',
        email: 'diana@example.com',
        age: 30,
        tags: ['hero']
    });
    console.log(`Added user_004: ${store.get('user_004').name}`);
    
    // Flush and close
    store.close();
    console.log(`\nData saved to: ${dataPath}/collections/users/`);
}

function exampleBulkWriter(dataPath) {
    console.log('\n' + '='.repeat(60));
    console.log('Example 2: Bulk Writer (High-throughput Ingestion)');
    console.log('='.repeat(60));
    
    // Create bulk writer
    const writer = BulkWriter.create(dataPath, 'products', 100);
    
    // Write many documents efficiently
    const startTime = Date.now();
    for (let i = 0; i < 1000; i++) {
        writer.put(`prod_${i.toString().padStart(4, '0')}`, {
            name: `Product ${i}`,
            price: Math.random() * 100,
            category: ['Electronics', 'Clothing', 'Books', 'Home'][i % 4],
            inStock: i % 2 === 0
        });
    }
    writer.flush();
    const elapsed = Date.now() - startTime;
    
    console.log(`Wrote ${writer.count} documents in ${elapsed}ms`);
    console.log(`Rate: ${Math.round(writer.count / (elapsed / 1000))} docs/sec`);
    console.log(`\nData saved to: ${dataPath}/collections/products/`);
}

function exampleRawJsonl(dataPath) {
    console.log('\n' + '='.repeat(60));
    console.log('Example 3: Raw JSONL Operations (Fastest Path)');
    console.log('='.repeat(60));
    
    // Create store
    const store = ZdsStore.open(dataPath, 'logs');
    
    // Write documents first
    for (let i = 0; i < 100; i++) {
        store.put(`log_${i.toString().padStart(4, '0')}`, {
            timestamp: new Date().toISOString(),
            level: ['INFO', 'WARN', 'ERROR'][i % 3],
            message: `Log message ${i}`
        });
    }
    store.flush();
    
    // Read entire JSONL blob (fastest read)
    const blob = store.readJsonlBlob();
    console.log(`Read JSONL blob: ${blob.length} bytes`);
    
    // Parse it
    const lines = blob.toString().trim().split('\n');
    console.log(`Contains ${lines.length} documents`);
    
    // scanRaw returns array of Buffer for each doc
    const rawDocs = store.scanRaw();
    console.log(`scanRaw returned ${rawDocs.length} documents`);
    
    store.close();
    console.log(`\nData saved to: ${dataPath}/collections/logs/`);
}

function exampleStoreInfo(dataPath) {
    console.log('\n' + '='.repeat(60));
    console.log('Example 4: Store Information');
    console.log('='.repeat(60));
    
    // Reopen stores and get info
    const usersStore = ZdsStore.open(dataPath, 'users');
    const productsStore = ZdsStore.open(dataPath, 'products');
    const logsStore = ZdsStore.open(dataPath, 'logs');
    
    for (const store of [usersStore, productsStore, logsStore]) {
        const info = store.info;
        console.log(`\nCollection: ${info.collection}`);
        console.log(`  Root: ${info.root}`);
        console.log(`  Documents: ${info.count}`);
    }
    
    usersStore.close();
    productsStore.close();
    logsStore.close();
}

function main() {
    console.log(`ZDS Version: ${version()}\n`);
    
    const dataPath = setupDataDir();
    console.log(`Output directory: ${dataPath}\n`);
    
    exampleBasicStore(dataPath);
    exampleBulkWriter(dataPath);
    exampleRawJsonl(dataPath);
    exampleStoreInfo(dataPath);
    
    console.log('\n' + '='.repeat(60));
    console.log('All examples completed successfully!');
    console.log(`Data saved to: ${DATA_DIR}`);
    console.log('='.repeat(60));
}

main();

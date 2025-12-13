#!/usr/bin/env node
/**
 * Streaming data examples with ZDS.
 * 
 * This script demonstrates:
 * - Streaming large datasets
 * - Batch processing
 * - Memory-efficient iteration
 * 
 * Output is saved to: examples/data/nodejs_02_streaming/
 * 
 * Run: node examples/nodejs/02_streaming_data.js
 */

const path = require('path');
const fs = require('fs');

const { ZdsStore, BulkWriter } = require('../../nodejs');

const DATA_DIR = path.join(__dirname, '..', 'data', 'nodejs_02_streaming');

function setupDataDir() {
    if (fs.existsSync(DATA_DIR)) {
        fs.rmSync(DATA_DIR, { recursive: true });
    }
    fs.mkdirSync(DATA_DIR, { recursive: true });
    return DATA_DIR;
}

function exampleCreateLargeDataset(dataPath) {
    console.log('='.repeat(60));
    console.log('Creating Large Dataset');
    console.log('='.repeat(60));
    
    const writer = BulkWriter.create(dataPath, 'events', 500);
    
    const startTime = Date.now();
    const count = 10000;
    
    for (let i = 0; i < count; i++) {
        writer.put(`event_${i.toString().padStart(6, '0')}`, {
            id: i,
            timestamp: new Date(Date.now() - Math.random() * 86400000).toISOString(),
            type: ['click', 'view', 'purchase', 'signup'][i % 4],
            userId: `user_${(i % 100).toString().padStart(3, '0')}`,
            value: Math.random() * 1000,
            metadata: {
                browser: ['Chrome', 'Firefox', 'Safari', 'Edge'][i % 4],
                platform: ['Windows', 'Mac', 'Linux', 'Mobile'][i % 4]
            }
        });
    }
    writer.flush();
    
    const elapsed = Date.now() - startTime;
    console.log(`Created ${writer.count} events in ${elapsed}ms`);
    console.log(`Rate: ${Math.round(count / (elapsed / 1000))} docs/sec`);
}

function exampleStreamProcessing(dataPath) {
    console.log('\n' + '='.repeat(60));
    console.log('Stream Processing Example');
    console.log('='.repeat(60));
    
    const store = ZdsStore.open(dataPath, 'events');
    
    // Count events by type
    const typeCounts = {};
    let totalValue = 0;
    
    const startTime = Date.now();
    
    // scan() returns all documents - process them
    const docs = store.scan();
    for (const doc of docs) {
        typeCounts[doc.type] = (typeCounts[doc.type] || 0) + 1;
        totalValue += doc.value;
    }
    
    const elapsed = Date.now() - startTime;
    
    console.log(`\nProcessed ${docs.length} documents in ${elapsed}ms`);
    console.log(`\nEvent counts by type:`);
    for (const [type, count] of Object.entries(typeCounts)) {
        console.log(`  ${type}: ${count}`);
    }
    console.log(`\nTotal value: ${totalValue.toFixed(2)}`);
    console.log(`Average value: ${(totalValue / docs.length).toFixed(2)}`);
    
    store.close();
}

function exampleBatchProcessing(dataPath) {
    console.log('\n' + '='.repeat(60));
    console.log('Batch Processing Example');
    console.log('='.repeat(60));
    
    const store = ZdsStore.open(dataPath, 'events');
    
    // Read all docs at once (faster for bulk operations)
    const allDocs = store.scan();
    
    // Process in batches of 1000
    const batchSize = 1000;
    let batchNum = 0;
    
    for (let i = 0; i < allDocs.length; i += batchSize) {
        const batch = allDocs.slice(i, i + batchSize);
        batchNum++;
        
        // Simulate batch processing
        const purchaseCount = batch.filter(d => d.type === 'purchase').length;
        const batchValue = batch.reduce((sum, d) => sum + d.value, 0);
        
        console.log(`Batch ${batchNum}: ${batch.length} docs, ${purchaseCount} purchases, value: ${batchValue.toFixed(2)}`);
    }
    
    store.close();
}

function exampleFilterAndTransform(dataPath) {
    console.log('\n' + '='.repeat(60));
    console.log('Filter and Transform Example');
    console.log('='.repeat(60));
    
    const sourceStore = ZdsStore.open(dataPath, 'events');
    const targetStore = ZdsStore.open(dataPath, 'purchases');
    
    // Filter purchases and transform
    const docs = sourceStore.scan();
    let count = 0;
    
    for (const doc of docs) {
        if (doc.type === 'purchase') {
            // Transform: extract key fields
            targetStore.put(`purchase_${count.toString().padStart(4, '0')}`, {
                originalId: `event_${doc.id.toString().padStart(6, '0')}`,
                userId: doc.userId,
                amount: doc.value,
                timestamp: doc.timestamp,
                browser: doc.metadata.browser
            });
            count++;
        }
    }
    
    targetStore.close();
    sourceStore.close();
    
    console.log(`Created ${count} purchase records`);
    console.log(`Data saved to: ${dataPath}/collections/purchases/`);
}

function exampleRawJsonlStream(dataPath) {
    console.log('\n' + '='.repeat(60));
    console.log('Raw JSONL Stream (Fastest Read)');
    console.log('='.repeat(60));
    
    const store = ZdsStore.open(dataPath, 'events');
    
    const startTime = Date.now();
    
    // Read entire file as blob - fastest for large datasets
    const blob = store.readJsonlBlob();
    const readTime = Date.now() - startTime;
    
    // Parse line by line
    const parseStart = Date.now();
    const lines = blob.toString().split('\n').filter(line => line.trim());
    const docs = lines.map(line => JSON.parse(line));
    const parseTime = Date.now() - parseStart;
    
    console.log(`Read ${blob.length} bytes in ${readTime}ms`);
    console.log(`Parsed ${docs.length} documents in ${parseTime}ms`);
    console.log(`Total time: ${readTime + parseTime}ms`);
    
    store.close();
}

function main() {
    const dataPath = setupDataDir();
    console.log(`Output directory: ${dataPath}\n`);
    
    exampleCreateLargeDataset(dataPath);
    exampleStreamProcessing(dataPath);
    exampleBatchProcessing(dataPath);
    exampleFilterAndTransform(dataPath);
    exampleRawJsonlStream(dataPath);
    
    console.log('\n' + '='.repeat(60));
    console.log('All examples completed successfully!');
    console.log(`Data saved to: ${DATA_DIR}`);
    console.log('='.repeat(60));
}

main();

/**
 * ZDS Node.js Benchmark Suite
 * 
 * Compares ZDS against disk-backed storage solutions:
 * - ZDS Native Rust (JSONL + binary index via NAPI)
 * - SQLite (better-sqlite3)
 * - LevelDB (classic-level)
 * 
 * Methodology:
 * - Cold: Fresh store/connection open
 * - Warm: Store already open, measures operation only
 */

const fs = require('fs');
const path = require('path');
const { performance } = require('perf_hooks');

// =============================================================================
// Configuration
// =============================================================================

const DEFAULT_RECORDS = 100000;
const RANDOM_ACCESS_COUNT = 1000;

// =============================================================================
// Load Dependencies
// =============================================================================

let ZdsStore;
try {
    // Try platform-specific binding first
    const platform = process.platform;
    const arch = process.arch;
    let bindingPath;
    
    if (platform === 'darwin' && arch === 'arm64') {
        bindingPath = '../../nodejs/zippy-data.darwin-arm64.node';
    } else if (platform === 'darwin' && arch === 'x64') {
        bindingPath = '../../nodejs/zippy-data.darwin-x64.node';
    } else if (platform === 'linux' && arch === 'x64') {
        bindingPath = '../../nodejs/zippy-data.linux-x64-gnu.node';
    } else {
        bindingPath = '../../nodejs/zippy-data.node';
    }
    
    const binding = require(bindingPath);
    ZdsStore = binding.ZdsStore;
    console.log('✓ ZDS Native Rust loaded');
} catch (e) {
    console.log('✗ ZDS bindings not found:', e.message);
}

let Database;
try {
    Database = require('better-sqlite3');
    console.log('✓ SQLite (better-sqlite3) loaded');
} catch (e) {
    console.log('✗ better-sqlite3 not installed');
}

let Level;
try {
    Level = require('classic-level').ClassicLevel;
    console.log('✓ LevelDB (classic-level) loaded');
} catch (e) {
    console.log('✗ classic-level not installed');
}

// =============================================================================
// Utilities
// =============================================================================

function generateRecords(n) {
    const records = [];
    for (let i = 0; i < n; i++) {
        records.push({
            id: `record_${String(i).padStart(8, '0')}`,
            name: `User ${i}`,
            email: `user${i}@example.com`,
            age: Math.floor(Math.random() * 62) + 18,
            score: Math.round(Math.random() * 10000) / 100,
            active: Math.random() > 0.5,
            tags: ['a', 'b', 'c'].slice(0, Math.floor(Math.random() * 3) + 1),
            metadata: {
                created: `2025-01-${String((i % 28) + 1).padStart(2, '0')}`,
                source: ['web', 'mobile', 'api'][i % 3]
            }
        });
    }
    return records;
}

function getRandomIds(records, count) {
    const ids = [];
    const step = Math.floor(records.length / count);
    for (let i = 0; i < count; i++) {
        ids.push(records[i * step].id);
    }
    return ids;
}

function getDirSize(dirPath) {
    let size = 0;
    try {
        const files = fs.readdirSync(dirPath, { recursive: true });
        for (const file of files) {
            const filePath = path.join(dirPath, file);
            const stat = fs.statSync(filePath);
            if (stat.isFile()) size += stat.size;
        }
    } catch (e) {}
    return size / (1024 * 1024);
}

function cleanup(dirPath) {
    try {
        fs.rmSync(dirPath, { recursive: true, force: true });
    } catch (e) {}
}

function formatThroughput(t) {
    if (t >= 1000000) return `${(t / 1000000).toFixed(2)}M`;
    if (t >= 1000) return `${Math.round(t / 1000)}k`;
    return `${Math.round(t)}`;
}

// =============================================================================
// ZDS Native Rust Benchmarks
// =============================================================================

async function benchmarkZDS(records, tempDir) {
    if (!ZdsStore) return null;
    
    const results = {};
    const storePath = path.join(tempDir, 'zds');
    cleanup(storePath);
    
    // Write
    let details = {};
    let start = performance.now();
    const store = ZdsStore.open(storePath, 'benchmark', records.length + 1000);
    details.open = performance.now() - start;
    
    const docIds = records.map(r => r.id);
    const jsonlBlob = Buffer.from(
        records.map(r => JSON.stringify({ _id: r.id, ...r })).join('\n')
    );
    
    start = performance.now();
    store.writeJsonl(jsonlBlob, docIds);
    details.write = performance.now() - start;
    
    start = performance.now();
    store.flush();
    details.flush = performance.now() - start;
    
    const writeTotal = details.open + details.write + details.flush;
    results.write = {
        mode: 'cold',
        time_ms: writeTotal,
        throughput: records.length / (writeTotal / 1000),
        details,
        size_mb: getDirSize(storePath)
    };
    
    // Read All Cold
    details = {};
    start = performance.now();
    const store2 = ZdsStore.open(storePath, 'benchmark', 1000);
    details.open = performance.now() - start;
    
    start = performance.now();
    const blob = store2.readJsonlBlob();
    const lines = blob.toString().split('\n').filter(l => l.trim());
    const docs = lines.map(l => JSON.parse(l));
    details.scan = performance.now() - start;
    
    const readColdTotal = details.open + details.scan;
    results.read_all_cold = {
        mode: 'cold',
        time_ms: readColdTotal,
        throughput: docs.length / (readColdTotal / 1000),
        details
    };
    
    // Read All Warm
    details = {};
    start = performance.now();
    const blob2 = store2.readJsonlBlob();
    const lines2 = blob2.toString().split('\n').filter(l => l.trim());
    const docs2 = lines2.map(l => JSON.parse(l));
    details.scan = performance.now() - start;
    
    results.read_all_warm = {
        mode: 'warm',
        time_ms: details.scan,
        throughput: docs2.length / (details.scan / 1000),
        details
    };
    
    // Random Cold
    const ids = getRandomIds(records, RANDOM_ACCESS_COUNT);
    details = {};
    start = performance.now();
    const store3 = ZdsStore.open(storePath, 'benchmark', 1000);
    details.open = performance.now() - start;
    
    start = performance.now();
    const randomDocs = ids.map(id => store3.get(id)).filter(d => d);
    details.lookup = performance.now() - start;
    
    const randomColdTotal = details.open + details.lookup;
    results.random_cold = {
        mode: 'cold',
        time_ms: randomColdTotal,
        throughput: randomDocs.length / (randomColdTotal / 1000),
        details
    };
    
    // Random Warm
    details = {};
    start = performance.now();
    const randomDocs2 = ids.map(id => store3.get(id)).filter(d => d);
    details.lookup = performance.now() - start;
    
    results.random_warm = {
        mode: 'warm',
        time_ms: details.lookup,
        throughput: randomDocs2.length / (details.lookup / 1000),
        details
    };
    
    return results;
}

// =============================================================================
// SQLite Benchmarks
// =============================================================================

async function benchmarkSQLite(records, tempDir) {
    if (!Database) return null;
    
    const results = {};
    const dbPath = path.join(tempDir, 'sqlite.db');
    cleanup(dbPath);
    
    // Write
    let details = {};
    let start = performance.now();
    const db = new Database(dbPath);
    db.pragma('journal_mode = WAL');
    db.pragma('synchronous = NORMAL');
    db.exec(`
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    `);
    details.setup = performance.now() - start;
    
    const insert = db.prepare('INSERT INTO documents (id, data) VALUES (?, ?)');
    start = performance.now();
    const insertMany = db.transaction((records) => {
        for (const r of records) {
            insert.run(r.id, JSON.stringify(r));
        }
    });
    insertMany(records);
    details.insert = performance.now() - start;
    db.close();
    
    const writeTotal = details.setup + details.insert;
    results.write = {
        mode: 'cold',
        time_ms: writeTotal,
        throughput: records.length / (writeTotal / 1000),
        details,
        size_mb: fs.statSync(dbPath).size / (1024 * 1024)
    };
    
    // Read All Cold
    details = {};
    start = performance.now();
    const db2 = new Database(dbPath);
    details.open = performance.now() - start;
    
    start = performance.now();
    const rows = db2.prepare('SELECT data FROM documents').all();
    const docs = rows.map(r => JSON.parse(r.data));
    details.query = performance.now() - start;
    
    const readColdTotal = details.open + details.query;
    results.read_all_cold = {
        mode: 'cold',
        time_ms: readColdTotal,
        throughput: docs.length / (readColdTotal / 1000),
        details
    };
    
    // Read All Warm
    details = {};
    start = performance.now();
    const rows2 = db2.prepare('SELECT data FROM documents').all();
    const docs2 = rows2.map(r => JSON.parse(r.data));
    details.query = performance.now() - start;
    
    results.read_all_warm = {
        mode: 'warm',
        time_ms: details.query,
        throughput: docs2.length / (details.query / 1000),
        details
    };
    
    // Random Cold
    const ids = getRandomIds(records, RANDOM_ACCESS_COUNT);
    details = {};
    start = performance.now();
    const db3 = new Database(dbPath);
    details.open = performance.now() - start;
    
    const getStmt = db3.prepare('SELECT data FROM documents WHERE id = ?');
    start = performance.now();
    const randomDocs = [];
    for (const id of ids) {
        const row = getStmt.get(id);
        if (row) randomDocs.push(JSON.parse(row.data));
    }
    details.lookup = performance.now() - start;
    
    const randomColdTotal = details.open + details.lookup;
    results.random_cold = {
        mode: 'cold',
        time_ms: randomColdTotal,
        throughput: randomDocs.length / (randomColdTotal / 1000),
        details
    };
    
    // Random Warm
    details = {};
    start = performance.now();
    const randomDocs2 = [];
    for (const id of ids) {
        const row = getStmt.get(id);
        if (row) randomDocs2.push(JSON.parse(row.data));
    }
    details.lookup = performance.now() - start;
    
    results.random_warm = {
        mode: 'warm',
        time_ms: details.lookup,
        throughput: randomDocs2.length / (details.lookup / 1000),
        details
    };
    
    db2.close();
    db3.close();
    
    return results;
}

// =============================================================================
// LevelDB Benchmarks
// =============================================================================

async function benchmarkLevelDB(records, tempDir) {
    if (!Level) return null;
    
    const results = {};
    const dbPath = path.join(tempDir, 'leveldb');
    cleanup(dbPath);
    
    // Write
    let details = {};
    let start = performance.now();
    let db = new Level(dbPath, { valueEncoding: 'json' });
    await db.open();
    details.open = performance.now() - start;
    
    start = performance.now();
    const batch = db.batch();
    for (const r of records) {
        batch.put(r.id, r);
    }
    await batch.write();
    details.write = performance.now() - start;
    await db.close();
    
    const writeTotal = details.open + details.write;
    results.write = {
        mode: 'cold',
        time_ms: writeTotal,
        throughput: records.length / (writeTotal / 1000),
        details,
        size_mb: getDirSize(dbPath)
    };
    
    // Read All Cold
    details = {};
    start = performance.now();
    db = new Level(dbPath, { valueEncoding: 'json' });
    await db.open();
    details.open = performance.now() - start;
    
    start = performance.now();
    const docs = [];
    for await (const [key, value] of db.iterator()) {
        docs.push(value);
    }
    details.iterate = performance.now() - start;
    
    const readColdTotal = details.open + details.iterate;
    results.read_all_cold = {
        mode: 'cold',
        time_ms: readColdTotal,
        throughput: docs.length / (readColdTotal / 1000),
        details
    };
    
    // Read All Warm (reuse same db)
    details = {};
    start = performance.now();
    const docs2 = [];
    for await (const [key, value] of db.iterator()) {
        docs2.push(value);
    }
    details.iterate = performance.now() - start;
    
    results.read_all_warm = {
        mode: 'warm',
        time_ms: details.iterate,
        throughput: docs2.length / (details.iterate / 1000),
        details
    };
    
    // Random Warm (same db instance)
    const ids = getRandomIds(records, RANDOM_ACCESS_COUNT);
    details = {};
    start = performance.now();
    const randomDocs = [];
    for (const id of ids) {
        try {
            const doc = await db.get(id);
            randomDocs.push(doc);
        } catch (e) {}
    }
    details.lookup = performance.now() - start;
    
    results.random_warm = {
        mode: 'warm',
        time_ms: details.lookup,
        throughput: randomDocs.length / (details.lookup / 1000),
        details
    };
    
    await db.close();
    
    // Random Cold (fresh open)
    details = {};
    start = performance.now();
    db = new Level(dbPath, { valueEncoding: 'json' });
    await db.open();
    details.open = performance.now() - start;
    
    start = performance.now();
    const randomDocs2 = [];
    for (const id of ids) {
        try {
            const doc = await db.get(id);
            randomDocs2.push(doc);
        } catch (e) {}
    }
    details.lookup = performance.now() - start;
    
    const randomColdTotal = details.open + details.lookup;
    results.random_cold = {
        mode: 'cold',
        time_ms: randomColdTotal,
        throughput: randomDocs2.length / (randomColdTotal / 1000),
        details
    };
    
    await db.close();
    
    return results;
}

// =============================================================================
// Main
// =============================================================================

function printResult(name, results) {
    if (!results) return;
    
    console.log(`\n[${name}]`);
    
    if (results.write) {
        const r = results.write;
        const d = r.details;
        console.log(`  write:       ${formatThroughput(r.throughput).padStart(8)} rec/s  (${r.time_ms.toFixed(0)}ms) [${Object.entries(d).map(([k,v]) => `${k}:${v.toFixed(0)}`).join(', ')}]`);
    }
    
    if (results.read_all_cold) {
        const r = results.read_all_cold;
        const d = r.details;
        console.log(`  read_all:    ${formatThroughput(r.throughput).padStart(8)} rec/s  (${r.time_ms.toFixed(0)}ms) [${Object.entries(d).map(([k,v]) => `${k}:${v.toFixed(0)}`).join(', ')}] (cold)`);
    }
    
    if (results.read_all_warm) {
        const r = results.read_all_warm;
        const d = r.details;
        console.log(`  read_all:    ${formatThroughput(r.throughput).padStart(8)} rec/s  (${r.time_ms.toFixed(0)}ms) [${Object.entries(d).map(([k,v]) => `${k}:${v.toFixed(0)}`).join(', ')}] (warm)`);
    }
    
    if (results.random_cold) {
        const r = results.random_cold;
        const d = r.details;
        console.log(`  random:      ${formatThroughput(r.throughput).padStart(8)} rec/s  (${r.time_ms.toFixed(0)}ms) [${Object.entries(d).map(([k,v]) => `${k}:${v.toFixed(0)}`).join(', ')}] (cold)`);
    }
    
    if (results.random_warm) {
        const r = results.random_warm;
        const d = r.details;
        console.log(`  random:      ${formatThroughput(r.throughput).padStart(8)} rec/s  (${r.time_ms.toFixed(0)}ms) [${Object.entries(d).map(([k,v]) => `${k}:${v.toFixed(0)}`).join(', ')}] (warm)`);
    }
}

function printSummaryTable(allResults) {
    console.log('\n' + '='.repeat(70));
    console.log('SUMMARY TABLE');
    console.log('='.repeat(70) + '\n');
    
    const approaches = Object.keys(allResults).filter(k => allResults[k]);
    
    // Write
    console.log('### WRITE');
    console.log('| Approach | Throughput | Time |');
    console.log('|----------|------------|------|');
    for (const name of approaches) {
        const r = allResults[name]?.write;
        if (r) {
            console.log(`| ${name.padEnd(12)} | ${formatThroughput(r.throughput).padStart(10)} rec/s | ${r.time_ms.toFixed(0)}ms |`);
        }
    }
    
    // Read All
    console.log('\n### READ ALL');
    console.log('| Approach | Cold | Warm |');
    console.log('|----------|------|------|');
    for (const name of approaches) {
        const cold = allResults[name]?.read_all_cold;
        const warm = allResults[name]?.read_all_warm;
        const coldStr = cold ? `${formatThroughput(cold.throughput)} rec/s` : 'N/A';
        const warmStr = warm ? `${formatThroughput(warm.throughput)} rec/s` : 'N/A';
        console.log(`| ${name.padEnd(12)} | ${coldStr.padStart(12)} | ${warmStr.padStart(12)} |`);
    }
    
    // Random
    console.log('\n### RANDOM ACCESS');
    console.log('| Approach | Cold | Warm |');
    console.log('|----------|------|------|');
    for (const name of approaches) {
        const cold = allResults[name]?.random_cold;
        const warm = allResults[name]?.random_warm;
        const coldStr = cold ? `${formatThroughput(cold.throughput)} rec/s` : 'N/A';
        const warmStr = warm ? `${formatThroughput(warm.throughput)} rec/s` : 'N/A';
        console.log(`| ${name.padEnd(12)} | ${coldStr.padStart(12)} | ${warmStr.padStart(12)} |`);
    }
    
    // Storage
    console.log('\n### STORAGE SIZE');
    console.log('| Approach | Size |');
    console.log('|----------|------|');
    for (const name of approaches) {
        const r = allResults[name]?.write;
        if (r?.size_mb) {
            console.log(`| ${name.padEnd(12)} | ${r.size_mb.toFixed(1)} MB |`);
        }
    }
}

async function main() {
    const args = process.argv.slice(2);
    let nRecords = DEFAULT_RECORDS;
    
    for (const arg of args) {
        if (arg.startsWith('-n=')) {
            nRecords = parseInt(arg.split('=')[1]);
        }
    }
    
    console.log(`\n${'='.repeat(70)}`);
    console.log(`ZDS Node.js Benchmark Suite - ${nRecords.toLocaleString()} records`);
    console.log('='.repeat(70));
    
    console.log('\nGenerating test data...');
    const records = generateRecords(nRecords);
    console.log(`Generated ${records.length.toLocaleString()} records`);
    
    const tempDir = fs.mkdtempSync('/tmp/zds-bench-');
    
    try {
        const allResults = {};
        
        allResults['ZDS Native'] = await benchmarkZDS(records, tempDir);
        printResult('ZDS Native', allResults['ZDS Native']);
        
        allResults['SQLite'] = await benchmarkSQLite(records, tempDir);
        printResult('SQLite', allResults['SQLite']);
        
        allResults['LevelDB'] = await benchmarkLevelDB(records, tempDir);
        printResult('LevelDB', allResults['LevelDB']);
        
        printSummaryTable(allResults);
        
    } finally {
        cleanup(tempDir);
    }
}

main().catch(console.error);

/**
 * ZDS Store Tests
 * 
 * Comprehensive tests for the ZdsStore class.
 */

import { ZdsStore, ZdsRoot, BulkWriter, version } from '../index';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

describe('ZdsStore', () => {
    let testDir: string;
    
    beforeEach(() => {
        testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'zds-test-'));
    });
    
    afterEach(() => {
        fs.rmSync(testDir, { recursive: true, force: true });
    });
    
    describe('version', () => {
        it('should return version string', () => {
            expect(version()).toMatch(/^\d+\.\d+\.\d+/);
        });
    });
    
    describe('open', () => {
        it('should create a new store', () => {
            const store = ZdsStore.open(testDir, 'test');
            expect(store.count).toBe(0);
            store.close();
        });
        
        it('should create store with default collection', () => {
            const store = ZdsStore.open(testDir);
            expect(store.info.collection).toBe('default');
            store.close();
        });
        
        it('should reopen existing store', () => {
            const store1 = ZdsStore.open(testDir, 'test');
            store1.put('doc1', { value: 1 });
            store1.close();
            
            const store2 = ZdsStore.open(testDir, 'test');
            expect(store2.count).toBe(1);
            expect(store2.get('doc1')).toEqual({ value: 1 });
            store2.close();
        });
    });
    
    describe('put', () => {
        it('should store a document', () => {
            const store = ZdsStore.open(testDir, 'test');
            store.put('doc1', { text: 'hello', value: 42 });
            store.flush();
            
            expect(store.count).toBe(1);
            store.close();
        });
        
        it('should store documents with various types', () => {
            const store = ZdsStore.open(testDir, 'test');
            
            store.put('string', { value: 'hello' });
            store.put('number', { value: 42 });
            store.put('float', { value: 3.14 });
            store.put('boolean', { value: true });
            store.put('null', { value: null });
            store.put('array', { value: [1, 2, 3] });
            store.put('nested', { value: { deep: { nested: true } } });
            
            store.flush();
            expect(store.count).toBe(7);
            store.close();
        });
        
        it('should update existing document', () => {
            const store = ZdsStore.open(testDir, 'test');
            
            store.put('doc1', { value: 1 });
            store.put('doc1', { value: 2 });
            store.flush();
            
            // Note: JSONL append-only means old version exists but index points to new
            expect(store.get('doc1')).toEqual({ value: 2 });
            store.close();
        });
    });
    
    describe('get', () => {
        it('should retrieve stored document', () => {
            const store = ZdsStore.open(testDir, 'test');
            store.put('doc1', { text: 'hello', value: 42 });
            store.flush();
            
            const doc = store.get('doc1');
            expect(doc).toEqual({ text: 'hello', value: 42 });
            store.close();
        });
        
        it('should throw for non-existent document', () => {
            const store = ZdsStore.open(testDir, 'test');
            
            expect(() => store.get('nonexistent')).toThrow();
            store.close();
        });
        
        it('should handle nested objects', () => {
            const store = ZdsStore.open(testDir, 'test');
            const nested = {
                level1: {
                    level2: {
                        level3: {
                            value: 'deep'
                        }
                    }
                }
            };
            
            store.put('nested', nested);
            store.flush();
            
            const retrieved = store.get('nested');
            expect(retrieved).toEqual(nested);
            store.close();
        });
    });
    
    describe('exists', () => {
        it('should return true for existing document', () => {
            const store = ZdsStore.open(testDir, 'test');
            store.put('doc1', { value: 1 });
            store.flush();
            
            expect(store.exists('doc1')).toBe(true);
            store.close();
        });
        
        it('should return false for non-existent document', () => {
            const store = ZdsStore.open(testDir, 'test');
            
            expect(store.exists('nonexistent')).toBe(false);
            store.close();
        });
    });
    
    describe('delete', () => {
        it('should delete a document', () => {
            const store = ZdsStore.open(testDir, 'test');
            store.put('doc1', { value: 1 });
            store.flush();
            
            store.delete('doc1');
            
            expect(store.exists('doc1')).toBe(false);
            store.close();
        });
        
        it('should throw for non-existent document', () => {
            const store = ZdsStore.open(testDir, 'test');
            
            expect(() => store.delete('nonexistent')).toThrow();
            store.close();
        });
    });
    
    describe('scan', () => {
        it('should return all documents', () => {
            const store = ZdsStore.open(testDir, 'test');
            store.put('doc1', { value: 1 });
            store.put('doc2', { value: 2 });
            store.put('doc3', { value: 3 });
            store.flush();
            
            const docs = store.scan();
            expect(docs.length).toBe(3);
            store.close();
        });
        
        it('should return empty array for empty store', () => {
            const store = ZdsStore.open(testDir, 'test');
            
            const docs = store.scan();
            expect(docs).toEqual([]);
            store.close();
        });
    });
    
    describe('listDocIds', () => {
        it('should return all document IDs', () => {
            const store = ZdsStore.open(testDir, 'test');
            store.put('doc1', { value: 1 });
            store.put('doc2', { value: 2 });
            store.flush();
            
            const ids = store.listDocIds();
            expect(ids).toContain('doc1');
            expect(ids).toContain('doc2');
            store.close();
        });
    });
    
    describe('count', () => {
        it('should return correct count', () => {
            const store = ZdsStore.open(testDir, 'test');
            
            expect(store.count).toBe(0);
            
            store.put('doc1', { value: 1 });
            store.put('doc2', { value: 2 });
            store.flush();
            
            expect(store.count).toBe(2);
            store.close();
        });
    });
    
    describe('info', () => {
        it('should return store info', () => {
            const store = ZdsStore.open(testDir, 'test');
            store.put('doc1', { value: 1 });
            store.flush();
            
            const info = store.info;
            expect(info.root).toBe(testDir);
            expect(info.collection).toBe('test');
            expect(info.count).toBe(1);
            store.close();
        });
    });
});

describe('BulkWriter', () => {
    let testDir: string;
    
    beforeEach(() => {
        testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'zds-bulk-test-'));
    });
    
    afterEach(() => {
        fs.rmSync(testDir, { recursive: true, force: true });
    });
    
    it('should write many documents efficiently', () => {
        const writer = BulkWriter.create(testDir, 'bulk', 100);
        
        for (let i = 0; i < 1000; i++) {
            writer.put(`doc_${i}`, { index: i, value: i * 2 });
        }
        writer.flush();
        
        expect(writer.count).toBe(1000);
    });
    
    it('should auto-flush at batch size', () => {
        const writer = BulkWriter.create(testDir, 'bulk', 10);
        
        for (let i = 0; i < 25; i++) {
            writer.put(`doc_${i}`, { index: i });
        }
        writer.flush();
        
        expect(writer.count).toBe(25);
    });
});

describe('Raw JSONL Operations', () => {
    let testDir: string;
    
    beforeEach(() => {
        testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'zds-raw-test-'));
    });
    
    afterEach(() => {
        fs.rmSync(testDir, { recursive: true, force: true });
    });
    
    describe('writeJsonl', () => {
        it('should write JSONL blob', () => {
            const store = ZdsStore.open(testDir, 'test');
            
            const lines = [
                JSON.stringify({ _id: 'doc1', value: 1 }),
                JSON.stringify({ _id: 'doc2', value: 2 })
            ].join('\n');
            
            const count = store.writeJsonl(Buffer.from(lines), ['doc1', 'doc2']);
            store.flush();
            
            expect(count).toBe(2);
            expect(store.get('doc1')).toEqual({ value: 1 });
            store.close();
        });
    });
    
    describe('readJsonlBlob', () => {
        it('should read entire JSONL as buffer', () => {
            const store = ZdsStore.open(testDir, 'test');
            store.put('doc1', { value: 1 });
            store.put('doc2', { value: 2 });
            store.flush();
            
            const blob = store.readJsonlBlob();
            expect(blob).toBeInstanceOf(Buffer);
            expect(blob.length).toBeGreaterThan(0);
            
            // Parse and verify
            const lines = blob.toString().trim().split('\n');
            expect(lines.length).toBe(2);
            store.close();
        });
    });
    
    describe('scanRaw', () => {
        it('should return array of buffers', () => {
            const store = ZdsStore.open(testDir, 'test');
            store.put('doc1', { value: 1 });
            store.put('doc2', { value: 2 });
            store.flush();
            
            const raw = store.scanRaw();
            expect(raw.length).toBe(2);
            expect(raw[0]).toBeInstanceOf(Buffer);
            store.close();
        });
    });
});

describe('Persistence', () => {
    let testDir: string;
    
    beforeEach(() => {
        testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'zds-persist-test-'));
    });
    
    afterEach(() => {
        fs.rmSync(testDir, { recursive: true, force: true });
    });
    
    it('should persist data across sessions', () => {
        // Session 1: Write data
        const store1 = ZdsStore.open(testDir, 'test');
        store1.put('doc1', { session: 1, value: 'first' });
        store1.put('doc2', { session: 1, value: 'second' });
        store1.close();
        
        // Session 2: Read and verify
        const store2 = ZdsStore.open(testDir, 'test');
        expect(store2.count).toBe(2);
        expect(store2.get('doc1')).toEqual({ session: 1, value: 'first' });
        expect(store2.get('doc2')).toEqual({ session: 1, value: 'second' });
        
        // Session 2: Add more data
        store2.put('doc3', { session: 2, value: 'third' });
        store2.close();
        
        // Session 3: Verify all data
        const store3 = ZdsStore.open(testDir, 'test');
        expect(store3.count).toBe(3);
        store3.close();
    });
});

describe('ZdsRoot', () => {
    let testDir: string;
    
    beforeEach(() => {
        testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'zds-root-test-'));
    });
    
    afterEach(() => {
        fs.rmSync(testDir, { recursive: true, force: true });
    });
    
    describe('open', () => {
        it('should create a new root', () => {
            const root = ZdsRoot.open(testDir);
            expect(root.rootPath).toBe(testDir);
            expect(root.listCollections()).toEqual([]);
        });
        
        it('should accept custom batch size', () => {
            const root = ZdsRoot.open(testDir, 10000);
            expect(root.batchSize).toBe(10000);
        });
    });
    
    describe('collection', () => {
        it('should create and return a collection handle', () => {
            const root = ZdsRoot.open(testDir);
            const train = root.collection('train');
            
            train.put('doc1', { value: 1 });
            train.flush();
            
            expect(train.count).toBe(1);
            expect(root.collectionExists('train')).toBe(true);
        });
        
        it('should support custom batch size per collection', () => {
            const root = ZdsRoot.open(testDir);
            const train = root.collection('train', 500);
            
            train.put('doc1', { value: 1 });
            train.flush();
            
            expect(train.count).toBe(1);
        });
    });
    
    describe('multiple collections', () => {
        it('should manage multiple collections from same root', () => {
            const root = ZdsRoot.open(testDir);
            
            const train = root.collection('train');
            const test = root.collection('test');
            const valid = root.collection('validation');
            
            train.put('doc1', { split: 'train', value: 1 });
            test.put('doc1', { split: 'test', value: 2 });
            valid.put('doc1', { split: 'validation', value: 3 });
            
            train.flush();
            test.flush();
            valid.flush();
            
            // Verify each collection has its own data
            expect(train.get('doc1')).toEqual({ split: 'train', value: 1 });
            expect(test.get('doc1')).toEqual({ split: 'test', value: 2 });
            expect(valid.get('doc1')).toEqual({ split: 'validation', value: 3 });
            
            // List collections
            const collections = root.listCollections();
            expect(collections).toContain('train');
            expect(collections).toContain('test');
            expect(collections).toContain('validation');
            expect(collections.length).toBe(3);
        });
        
        it('should isolate collections from each other', () => {
            const root = ZdsRoot.open(testDir);
            
            const train = root.collection('train');
            const test = root.collection('test');
            
            // Write same doc ID to different collections
            train.put('doc_001', { value: 100 });
            test.put('doc_001', { value: 200 });
            
            train.flush();
            test.flush();
            
            // Each collection should have independent data
            expect(train.get('doc_001')).toEqual({ value: 100 });
            expect(test.get('doc_001')).toEqual({ value: 200 });
        });
        
        it('should not leak documents between collections', () => {
            const root = ZdsRoot.open(testDir);
            
            const train = root.collection('train');
            const test = root.collection('test');
            
            train.put('train_only', { exists_in: 'train' });
            test.put('test_only', { exists_in: 'test' });
            
            train.flush();
            test.flush();
            
            // Verify docs don't exist in wrong collection
            expect(() => train.get('test_only')).toThrow();
            expect(() => test.get('train_only')).toThrow();
        });
    });
    
    describe('collectionExists', () => {
        it('should return false for non-existent collection', () => {
            const root = ZdsRoot.open(testDir);
            expect(root.collectionExists('nonexistent')).toBe(false);
        });
        
        it('should return true after creating collection', () => {
            const root = ZdsRoot.open(testDir);
            
            expect(root.collectionExists('train')).toBe(false);
            
            const train = root.collection('train');
            train.put('doc1', { test: true });
            train.flush();
            
            expect(root.collectionExists('train')).toBe(true);
        });
    });
    
    describe('info', () => {
        it('should return root info', () => {
            const root = ZdsRoot.open(testDir, 5000);
            
            root.collection('train').put('doc1', { value: 1 });
            root.collection('test').put('doc1', { value: 2 });
            
            const info = root.info;
            expect(info.root).toBe(testDir);
            expect(info.batchSize).toBe(5000);
            expect(info.collections).toContain('train');
            expect(info.collections).toContain('test');
        });
    });
    
    describe('persistence', () => {
        it('should persist collections across sessions', () => {
            // Session 1: Create collections
            const root1 = ZdsRoot.open(testDir);
            const train1 = root1.collection('train');
            train1.put('doc1', { persisted: true });
            train1.close();
            
            // Session 2: Reopen and verify
            const root2 = ZdsRoot.open(testDir);
            expect(root2.collectionExists('train')).toBe(true);
            
            const train2 = root2.collection('train');
            expect(train2.get('doc1')).toEqual({ persisted: true });
            train2.close();
        });
    });
});

describe('ZdsRoot vs ZdsStore.open compatibility', () => {
    let testDir: string;
    
    beforeEach(() => {
        testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'zds-compat-test-'));
    });
    
    afterEach(() => {
        fs.rmSync(testDir, { recursive: true, force: true });
    });
    
    it('should allow reading data written via ZdsRoot from ZdsStore.open', () => {
        // Write via ZdsRoot
        const root = ZdsRoot.open(testDir);
        const train = root.collection('train');
        train.put('doc1', { source: 'root' });
        train.close();
        
        // Read via ZdsStore.open
        const store = ZdsStore.open(testDir, 'train');
        expect(store.get('doc1')).toEqual({ source: 'root' });
        store.close();
    });
    
    it('should allow reading data written via ZdsStore.open from ZdsRoot', () => {
        // Write via ZdsStore.open
        const store = ZdsStore.open(testDir, 'train');
        store.put('doc1', { source: 'store' });
        store.close();
        
        // Read via ZdsRoot
        const root = ZdsRoot.open(testDir);
        const train = root.collection('train');
        expect(train.get('doc1')).toEqual({ source: 'store' });
        train.close();
    });
});

/**
 * ZDS Store Tests
 * 
 * Comprehensive tests for the ZdsStore class.
 */

import { ZdsStore, BulkWriter, version } from '../index';
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

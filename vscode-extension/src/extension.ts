import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

// ZDS Store abstraction
class ZDSStore {
    private rootPath: string;
    private collection: string;

    constructor(rootPath: string, collection: string = 'default') {
        this.rootPath = rootPath;
        this.collection = collection;
    }

    get collectionsPath(): string {
        return path.join(this.rootPath, 'collections');
    }

    get collectionPath(): string {
        return path.join(this.collectionsPath, this.collection);
    }

    get docsPath(): string {
        return path.join(this.collectionPath, 'docs');
    }

    get metaPath(): string {
        return path.join(this.collectionPath, 'meta');
    }

    get manifestPath(): string {
        return path.join(this.collectionPath, 'meta', 'manifest.json');
    }

    get orderPath(): string {
        return path.join(this.collectionPath, 'meta', 'order.ids');
    }

    isValid(): boolean {
        return fs.existsSync(this.collectionsPath);
    }

    listCollections(): string[] {
        if (!fs.existsSync(this.collectionsPath)) {
            return [];
        }
        return fs.readdirSync(this.collectionsPath).filter(name => {
            const collPath = path.join(this.collectionsPath, name);
            return fs.statSync(collPath).isDirectory();
        });
    }

    listDocuments(): string[] {
        if (!fs.existsSync(this.docsPath)) {
            return [];
        }
        return fs.readdirSync(this.docsPath)
            .filter(name => name.endsWith('.json'))
            .map(name => name.replace('.json', ''));
    }

    getDocument(docId: string): any | null {
        const docPath = path.join(this.docsPath, `${docId}.json`);
        if (!fs.existsSync(docPath)) {
            return null;
        }
        const content = fs.readFileSync(docPath, 'utf-8');
        return JSON.parse(content);
    }

    putDocument(docId: string, doc: any): void {
        if (!fs.existsSync(this.docsPath)) {
            fs.mkdirSync(this.docsPath, { recursive: true });
        }
        const docPath = path.join(this.docsPath, `${docId}.json`);
        fs.writeFileSync(docPath, JSON.stringify(doc, null, 2));
        this.updateOrder(docId, 'add');
    }

    deleteDocument(docId: string): boolean {
        const docPath = path.join(this.docsPath, `${docId}.json`);
        if (!fs.existsSync(docPath)) {
            return false;
        }
        fs.unlinkSync(docPath);
        this.updateOrder(docId, 'remove');
        return true;
    }

    private updateOrder(docId: string, action: 'add' | 'remove'): void {
        if (!fs.existsSync(this.metaPath)) {
            fs.mkdirSync(this.metaPath, { recursive: true });
        }

        let order: string[] = [];
        if (fs.existsSync(this.orderPath)) {
            const content = fs.readFileSync(this.orderPath, 'utf-8');
            order = content.split('\n').filter(id => id.trim());
        }

        if (action === 'add' && !order.includes(docId)) {
            order.push(docId);
        } else if (action === 'remove') {
            order = order.filter(id => id !== docId);
        }

        fs.writeFileSync(this.orderPath, order.join('\n') + '\n');
    }

    getStats(): any {
        const docs = this.listDocuments();
        let totalSize = 0;
        
        for (const docId of docs) {
            const docPath = path.join(this.docsPath, `${docId}.json`);
            if (fs.existsSync(docPath)) {
                totalSize += fs.statSync(docPath).size;
            }
        }

        return {
            collection: this.collection,
            documentCount: docs.length,
            totalSizeBytes: totalSize,
            totalSizeKB: (totalSize / 1024).toFixed(2)
        };
    }

    static initStore(rootPath: string): void {
        const collectionsPath = path.join(rootPath, 'collections');
        if (!fs.existsSync(collectionsPath)) {
            fs.mkdirSync(collectionsPath, { recursive: true });
        }
    }

    static initCollection(rootPath: string, collection: string): void {
        const store = new ZDSStore(rootPath, collection);
        
        if (!fs.existsSync(store.docsPath)) {
            fs.mkdirSync(store.docsPath, { recursive: true });
        }
        if (!fs.existsSync(store.metaPath)) {
            fs.mkdirSync(store.metaPath, { recursive: true });
        }

        // Create manifest
        const manifest = {
            version: '0.1.0',
            collection: collection,
            created: new Date().toISOString(),
            schema_mode: 'flexible'
        };
        fs.writeFileSync(store.manifestPath, JSON.stringify(manifest, null, 2));

        // Create empty order file
        fs.writeFileSync(store.orderPath, '');
    }
}

// Tree data providers
class CollectionTreeItem extends vscode.TreeItem {
    constructor(
        public readonly name: string,
        public readonly rootPath: string
    ) {
        super(name, vscode.TreeItemCollapsibleState.None);
        this.contextValue = 'collection';
        this.iconPath = new vscode.ThemeIcon('database');
        this.command = {
            command: 'zds.selectCollection',
            title: 'Select Collection',
            arguments: [this]
        };
    }
}

class DocumentTreeItem extends vscode.TreeItem {
    constructor(
        public readonly docId: string,
        public readonly rootPath: string,
        public readonly collection: string
    ) {
        super(docId, vscode.TreeItemCollapsibleState.None);
        this.contextValue = 'document';
        this.iconPath = new vscode.ThemeIcon('file');
        this.command = {
            command: 'zds.viewDocument',
            title: 'View Document',
            arguments: [this]
        };
    }
}

class CollectionProvider implements vscode.TreeDataProvider<CollectionTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<CollectionTreeItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    
    private rootPath: string | undefined;

    constructor() {
        this.rootPath = this.findZDSRoot();
    }

    private findZDSRoot(): string | undefined {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders) {
            return undefined;
        }

        for (const folder of workspaceFolders) {
            const store = new ZDSStore(folder.uri.fsPath);
            if (store.isValid()) {
                return folder.uri.fsPath;
            }
        }

        return workspaceFolders[0]?.uri.fsPath;
    }

    setRootPath(rootPath: string): void {
        this.rootPath = rootPath;
        this.refresh();
    }

    refresh(): void {
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: CollectionTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(): Thenable<CollectionTreeItem[]> {
        if (!this.rootPath) {
            return Promise.resolve([]);
        }

        const store = new ZDSStore(this.rootPath);
        const collections = store.listCollections();
        
        return Promise.resolve(
            collections.map(name => new CollectionTreeItem(name, this.rootPath!))
        );
    }

    getRootPath(): string | undefined {
        return this.rootPath;
    }
}

class DocumentProvider implements vscode.TreeDataProvider<DocumentTreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<DocumentTreeItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    
    private rootPath: string | undefined;
    private collection: string | undefined;

    setCollection(rootPath: string, collection: string): void {
        this.rootPath = rootPath;
        this.collection = collection;
        this.refresh();
    }

    refresh(): void {
        this._onDidChangeTreeData.fire(undefined);
    }

    getTreeItem(element: DocumentTreeItem): vscode.TreeItem {
        return element;
    }

    getChildren(): Thenable<DocumentTreeItem[]> {
        if (!this.rootPath || !this.collection) {
            return Promise.resolve([]);
        }

        const store = new ZDSStore(this.rootPath, this.collection);
        const docs = store.listDocuments();
        
        return Promise.resolve(
            docs.map(docId => new DocumentTreeItem(docId, this.rootPath!, this.collection!))
        );
    }

    getCollection(): string | undefined {
        return this.collection;
    }

    getRootPath(): string | undefined {
        return this.rootPath;
    }
}

// Document editor webview
class DocumentEditorPanel {
    public static currentPanel: DocumentEditorPanel | undefined;
    private readonly panel: vscode.WebviewPanel;
    private disposables: vscode.Disposable[] = [];

    private constructor(
        panel: vscode.WebviewPanel,
        private store: ZDSStore,
        private docId: string,
        private isNew: boolean
    ) {
        this.panel = panel;
        this.update();

        this.panel.onDidDispose(() => this.dispose(), null, this.disposables);
        
        this.panel.webview.onDidReceiveMessage(
            async message => {
                switch (message.command) {
                    case 'save':
                        try {
                            const doc = JSON.parse(message.content);
                            this.store.putDocument(this.docId, doc);
                            vscode.window.showInformationMessage(`Document '${this.docId}' saved.`);
                            vscode.commands.executeCommand('zds.refreshDocuments');
                        } catch (e: any) {
                            vscode.window.showErrorMessage(`Failed to save: ${e.message}`);
                        }
                        break;
                    case 'cancel':
                        this.panel.dispose();
                        break;
                }
            },
            null,
            this.disposables
        );
    }

    public static show(
        extensionUri: vscode.Uri,
        store: ZDSStore,
        docId: string,
        isNew: boolean = false
    ): void {
        const column = vscode.ViewColumn.One;

        if (DocumentEditorPanel.currentPanel) {
            DocumentEditorPanel.currentPanel.panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'zdsDocumentEditor',
            isNew ? `New: ${docId}` : `Edit: ${docId}`,
            column,
            {
                enableScripts: true,
                retainContextWhenHidden: true
            }
        );

        DocumentEditorPanel.currentPanel = new DocumentEditorPanel(panel, store, docId, isNew);
    }

    private update(): void {
        const doc = this.isNew ? {} : (this.store.getDocument(this.docId) || {});
        const indent = vscode.workspace.getConfiguration('zds').get('jsonIndent', 2);
        
        this.panel.webview.html = this.getHtml(JSON.stringify(doc, null, indent));
    }

    private getHtml(content: string): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZDS Document Editor</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            padding: 20px;
            background: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
        }
        h2 {
            margin-top: 0;
            color: var(--vscode-foreground);
        }
        #editor {
            width: 100%;
            height: 400px;
            font-family: monospace;
            font-size: 14px;
            padding: 10px;
            border: 1px solid var(--vscode-input-border);
            background: var(--vscode-input-background);
            color: var(--vscode-input-foreground);
            resize: vertical;
        }
        .buttons {
            margin-top: 15px;
        }
        button {
            padding: 8px 16px;
            margin-right: 10px;
            cursor: pointer;
            border: none;
            border-radius: 3px;
        }
        .save {
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }
        .save:hover {
            background: var(--vscode-button-hoverBackground);
        }
        .cancel {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }
        .error {
            color: var(--vscode-errorForeground);
            margin-top: 10px;
        }
        .info {
            color: var(--vscode-descriptionForeground);
            font-size: 12px;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <h2>Document: ${this.docId}</h2>
    <p class="info">Edit the JSON document below. Press Save to commit changes.</p>
    <textarea id="editor">${this.escapeHtml(content)}</textarea>
    <div id="error" class="error"></div>
    <div class="buttons">
        <button class="save" onclick="save()">Save</button>
        <button class="cancel" onclick="cancel()">Cancel</button>
    </div>
    <script>
        const vscode = acquireVsCodeApi();
        
        function validateJson(text) {
            try {
                JSON.parse(text);
                return null;
            } catch (e) {
                return e.message;
            }
        }
        
        function save() {
            const content = document.getElementById('editor').value;
            const error = validateJson(content);
            
            if (error) {
                document.getElementById('error').textContent = 'Invalid JSON: ' + error;
                return;
            }
            
            document.getElementById('error').textContent = '';
            vscode.postMessage({ command: 'save', content: content });
        }
        
        function cancel() {
            vscode.postMessage({ command: 'cancel' });
        }
        
        // Real-time validation
        document.getElementById('editor').addEventListener('input', function() {
            const error = validateJson(this.value);
            document.getElementById('error').textContent = error ? 'Invalid JSON: ' + error : '';
        });
    </script>
</body>
</html>`;
    }

    private escapeHtml(text: string): string {
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    private dispose(): void {
        DocumentEditorPanel.currentPanel = undefined;
        this.panel.dispose();
        while (this.disposables.length) {
            const d = this.disposables.pop();
            if (d) {
                d.dispose();
            }
        }
    }
}

// Extension activation
export function activate(context: vscode.ExtensionContext) {
    console.log('ZDS extension activated');

    const collectionProvider = new CollectionProvider();
    const documentProvider = new DocumentProvider();

    // Register tree views
    vscode.window.registerTreeDataProvider('zdsExplorer', collectionProvider);
    vscode.window.registerTreeDataProvider('zdsDocuments', documentProvider);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('zds.refreshExplorer', () => {
            collectionProvider.refresh();
        }),

        vscode.commands.registerCommand('zds.refreshDocuments', () => {
            documentProvider.refresh();
        }),

        vscode.commands.registerCommand('zds.selectCollection', (item: CollectionTreeItem) => {
            documentProvider.setCollection(item.rootPath, item.name);
            vscode.window.showInformationMessage(`Selected collection: ${item.name}`);
        }),

        vscode.commands.registerCommand('zds.openCollection', async () => {
            const uri = await vscode.window.showOpenDialog({
                canSelectFiles: false,
                canSelectFolders: true,
                canSelectMany: false,
                title: 'Select ZDS Store Folder'
            });

            if (uri && uri[0]) {
                collectionProvider.setRootPath(uri[0].fsPath);
            }
        }),

        vscode.commands.registerCommand('zds.createCollection', async () => {
            const rootPath = collectionProvider.getRootPath();
            if (!rootPath) {
                vscode.window.showErrorMessage('No ZDS store open');
                return;
            }

            const name = await vscode.window.showInputBox({
                prompt: 'Collection name',
                placeHolder: 'e.g., users, products, logs'
            });

            if (name) {
                ZDSStore.initStore(rootPath);
                ZDSStore.initCollection(rootPath, name);
                collectionProvider.refresh();
                vscode.window.showInformationMessage(`Collection '${name}' created`);
            }
        }),

        vscode.commands.registerCommand('zds.viewDocument', (item: DocumentTreeItem) => {
            const store = new ZDSStore(item.rootPath, item.collection);
            const doc = store.getDocument(item.docId);
            
            if (doc) {
                const indent = vscode.workspace.getConfiguration('zds').get('jsonIndent', 2);
                const content = JSON.stringify(doc, null, indent);
                
                vscode.workspace.openTextDocument({
                    content: content,
                    language: 'json'
                }).then(document => {
                    vscode.window.showTextDocument(document, { preview: true });
                });
            }
        }),

        vscode.commands.registerCommand('zds.editDocument', (item: DocumentTreeItem) => {
            const store = new ZDSStore(item.rootPath, item.collection);
            DocumentEditorPanel.show(context.extensionUri, store, item.docId, false);
        }),

        vscode.commands.registerCommand('zds.addDocument', async () => {
            const rootPath = documentProvider.getRootPath();
            const collection = documentProvider.getCollection();

            if (!rootPath || !collection) {
                vscode.window.showErrorMessage('No collection selected');
                return;
            }

            const docId = await vscode.window.showInputBox({
                prompt: 'Document ID',
                placeHolder: 'e.g., user_001, product_abc'
            });

            if (docId) {
                const store = new ZDSStore(rootPath, collection);
                DocumentEditorPanel.show(context.extensionUri, store, docId, true);
            }
        }),

        vscode.commands.registerCommand('zds.deleteDocument', async (item: DocumentTreeItem) => {
            const confirm = await vscode.window.showWarningMessage(
                `Delete document '${item.docId}'?`,
                { modal: true },
                'Delete'
            );

            if (confirm === 'Delete') {
                const store = new ZDSStore(item.rootPath, item.collection);
                if (store.deleteDocument(item.docId)) {
                    documentProvider.refresh();
                    vscode.window.showInformationMessage(`Document '${item.docId}' deleted`);
                }
            }
        }),

        vscode.commands.registerCommand('zds.showStats', (item: CollectionTreeItem) => {
            const store = new ZDSStore(item.rootPath, item.name);
            const stats = store.getStats();
            
            const message = [
                `Collection: ${stats.collection}`,
                `Documents: ${stats.documentCount}`,
                `Total Size: ${stats.totalSizeKB} KB`
            ].join('\n');

            vscode.window.showInformationMessage(message, { modal: true });
        }),

        vscode.commands.registerCommand('zds.exportCollection', async (item: CollectionTreeItem) => {
            const store = new ZDSStore(item.rootPath, item.name);
            const docs = store.listDocuments();
            
            const exportData: any[] = [];
            for (const docId of docs) {
                const doc = store.getDocument(docId);
                if (doc) {
                    exportData.push({ _id: docId, ...doc });
                }
            }

            const uri = await vscode.window.showSaveDialog({
                defaultUri: vscode.Uri.file(`${item.name}.json`),
                filters: { 'JSON': ['json'] }
            });

            if (uri) {
                fs.writeFileSync(uri.fsPath, JSON.stringify(exportData, null, 2));
                vscode.window.showInformationMessage(`Exported ${docs.length} documents to ${uri.fsPath}`);
            }
        }),

        vscode.commands.registerCommand('zds.importToCollection', async () => {
            const rootPath = documentProvider.getRootPath();
            const collection = documentProvider.getCollection();

            if (!rootPath || !collection) {
                vscode.window.showErrorMessage('No collection selected');
                return;
            }

            const uri = await vscode.window.showOpenDialog({
                canSelectFiles: true,
                canSelectFolders: false,
                canSelectMany: false,
                filters: { 'JSON': ['json'] },
                title: 'Select JSON file to import'
            });

            if (uri && uri[0]) {
                try {
                    const content = fs.readFileSync(uri[0].fsPath, 'utf-8');
                    const data = JSON.parse(content);
                    const store = new ZDSStore(rootPath, collection);
                    
                    let count = 0;
                    const items = Array.isArray(data) ? data : [data];
                    
                    for (const item of items) {
                        const docId = item._id || `import_${count}`;
                        const { _id, ...doc } = item;
                        store.putDocument(docId, doc);
                        count++;
                    }

                    documentProvider.refresh();
                    vscode.window.showInformationMessage(`Imported ${count} documents`);
                } catch (e: any) {
                    vscode.window.showErrorMessage(`Import failed: ${e.message}`);
                }
            }
        }),

        vscode.commands.registerCommand('zds.validateStore', () => {
            const rootPath = collectionProvider.getRootPath();
            if (!rootPath) {
                vscode.window.showErrorMessage('No ZDS store open');
                return;
            }

            const store = new ZDSStore(rootPath);
            if (store.isValid()) {
                const collections = store.listCollections();
                vscode.window.showInformationMessage(
                    `Valid ZDS store with ${collections.length} collection(s): ${collections.join(', ')}`
                );
            } else {
                vscode.window.showWarningMessage('Not a valid ZDS store');
            }
        })
    );

    // Auto-refresh on file changes
    if (vscode.workspace.getConfiguration('zds').get('autoRefresh', true)) {
        const watcher = vscode.workspace.createFileSystemWatcher('**/collections/**/*.json');
        watcher.onDidCreate(() => documentProvider.refresh());
        watcher.onDidDelete(() => documentProvider.refresh());
        watcher.onDidChange(() => documentProvider.refresh());
        context.subscriptions.push(watcher);
    }
}

export function deactivate() {}

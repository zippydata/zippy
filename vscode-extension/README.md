# Zippy ZDS Editor - VS Code Extension

A Visual Studio Code extension for viewing and editing ZDS (Zippy Data System) files and collections.

## Features

- **Collection Explorer**: Browse ZDS collections in the activity bar
- **Document Viewer**: View documents with syntax highlighting
- **Document Editor**: Edit documents with JSON validation
- **CRUD Operations**: Create, read, update, and delete documents
- **Import/Export**: Import JSON files into collections, export collections to JSON
- **Statistics**: View collection statistics (document count, size)
- **Auto-refresh**: Automatically refresh when files change

## Installation

### From Source

```bash
cd vscode-extension
npm install
npm run compile
```

Then press F5 in VS Code to launch the extension in development mode.

### From VSIX

```bash
cd vscode-extension
npm install
npm run package
# Install the generated .vsix file
code --install-extension zippy-zds-0.1.0.vsix
```

## Usage

### Opening a ZDS Store

1. Open a folder containing a ZDS store (has `collections/` directory)
2. The ZDS Explorer will appear in the activity bar
3. Click on a collection to view its documents

Or use the command palette:
- `ZDS: Open ZDS Collection` - Browse for a ZDS store folder

### Working with Documents

**View a document:**
- Click on a document in the Documents panel
- Or right-click → View Document

**Edit a document:**
- Right-click on a document → Edit Document
- Make changes in the editor panel
- Click Save to commit changes

**Add a document:**
- Click the + icon in the Documents panel title
- Enter a document ID
- Edit the JSON content
- Click Save

**Delete a document:**
- Right-click on a document → Delete Document
- Confirm the deletion

### Import/Export

**Export collection to JSON:**
- Right-click on a collection → Export Collection to JSON
- Choose a save location

**Import JSON to collection:**
- Select a collection
- Use command `ZDS: Import JSON to Collection`
- Select a JSON file (array of objects or single object)
- Objects with `_id` field will use that as the document ID

### Commands

| Command | Description |
|---------|-------------|
| `ZDS: Open ZDS Collection` | Open a ZDS store folder |
| `ZDS: Create ZDS Collection` | Create a new collection |
| `ZDS: Refresh ZDS Explorer` | Refresh the collection list |
| `ZDS: Add Document` | Add a new document to selected collection |
| `ZDS: View Document` | View a document (read-only) |
| `ZDS: Edit Document` | Edit a document |
| `ZDS: Delete Document` | Delete a document |
| `ZDS: Export Collection to JSON` | Export collection as JSON array |
| `ZDS: Import JSON to Collection` | Import JSON file into collection |
| `ZDS: Validate ZDS Store` | Check if current folder is valid ZDS store |
| `ZDS: Show Collection Statistics` | Show document count and size |

## Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `zds.defaultStorePath` | string | `""` | Default path to ZDS store |
| `zds.autoRefresh` | boolean | `true` | Auto-refresh on file changes |
| `zds.jsonIndent` | number | `2` | JSON indentation for display |

## ZDS Store Structure

```
my-store/
├── collections/
│   ├── users/
│   │   ├── docs/
│   │   │   ├── user_001.json
│   │   │   └── user_002.json
│   │   └── meta/
│   │       ├── manifest.json
│   │       └── order.ids
│   └── products/
│       ├── docs/
│       │   └── prod_001.json
│       └── meta/
│           ├── manifest.json
│           └── order.ids
```

## Requirements

- VS Code 1.85.0 or higher
- Node.js 18+ (for development)

## Development

```bash
# Install dependencies
npm install

# Compile TypeScript
npm run compile

# Watch for changes
npm run watch

# Run linter
npm run lint

# Package extension
npm run package
```

## License

MIT

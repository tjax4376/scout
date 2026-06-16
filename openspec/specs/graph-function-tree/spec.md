# graph-function-tree Specification

## Purpose
TBD - created by archiving change graph-function-tree-pane. Update Purpose after archive.
## Requirements
### Requirement: Function tree displays workspace hierarchy

The graph web UI SHALL display a hierarchical tree in the left pane showing directories, files, and code symbols (functions, methods, classes, modules) for the selected Scout space.

#### Scenario: Tree loads on space selection

- **WHEN** the user selects a space and the graph page finishes loading
- **THEN** the left pane SHALL populate a tree rooted at the workspace with expandable directory and file nodes and leaf symbol nodes

#### Scenario: Empty space shows message

- **WHEN** the symbols API returns no symbols for the selected space
- **THEN** the tree area SHALL display a clear empty-state message instead of a blank pane

### Requirement: Tree navigation focuses graph

The graph web UI SHALL navigate the Cytoscape graph when the user selects an item in the function tree.

#### Scenario: File selection loads file graph

- **WHEN** the user clicks a file node in the tree
- **THEN** the UI SHALL load the file graph using the existing file-graph flow and update the status bar accordingly

#### Scenario: Symbol selection focuses node

- **WHEN** the user clicks a symbol node (function, method, class, or module) in the tree
- **THEN** the UI SHALL focus that symbol in the graph canvas, show its details in the node detail panel, and highlight the corresponding graph node if present

#### Scenario: Graph selection syncs tree

- **WHEN** the user taps a node in the Cytoscape graph
- **THEN** the tree SHALL highlight the matching symbol or file entry and scroll it into view when possible

### Requirement: Tree supports expand and collapse

The function tree SHALL allow users to expand and collapse directory and file branches without reloading the page.

#### Scenario: Expand directory

- **WHEN** the user activates the expand control on a collapsed directory node
- **THEN** the directory SHALL reveal its child directories, files, and symbols

#### Scenario: Collapse directory

- **WHEN** the user activates the collapse control on an expanded directory node
- **THEN** the directory SHALL hide its descendants while remaining visible itself

### Requirement: Left pane is user-resizable

The graph web UI SHALL provide a vertical resize handle between the left pane and the graph canvas that users can adjust by click-and-drag.

#### Scenario: Drag resize handle

- **WHEN** the user presses the primary button on the resize handle and moves the pointer horizontally
- **THEN** the left pane width SHALL update in real time within configured minimum and maximum bounds

#### Scenario: Persist pane width

- **WHEN** the user releases the resize handle after adjusting pane width
- **THEN** the UI SHALL persist the width in browser local storage and restore it on subsequent page loads for the same browser

#### Scenario: Minimum width enforced

- **WHEN** the user attempts to resize the pane narrower than the minimum width (200px)
- **THEN** the pane SHALL stop shrinking at the minimum width

### Requirement: Tree uses existing symbols API

The function tree SHALL obtain symbol data from the existing `GET /v1/spaces/{space}/symbols` endpoint without requiring new server endpoints.

#### Scenario: Symbols fetched for space

- **WHEN** the tree initializes for a space
- **THEN** the client SHALL request symbols from `/v1/spaces/{space}/symbols` with an appropriate path prefix and build the hierarchy client-side

#### Scenario: Space change refreshes tree

- **WHEN** the user changes the selected space in the space dropdown
- **THEN** the tree SHALL clear prior content, fetch symbols for the new space, and rebuild the hierarchy


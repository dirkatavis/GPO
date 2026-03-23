# Glass Work Item Strategy Implementation Requirements

## Overview
Implementation of flexible work item handler pattern to handle different glass damage scenarios while maintaining reusability for future work item types (PM, Brake, etc.).

## Implementation Status: PHASE 1 COMPLETE

### Completed Components:

#### 1. WorkItemConfig Dataclass ✅

#### 2. WorkItemStrategy Base Class ✅ 
#### 2. WorkItemHandler Base Class ✅ 
 - **File**: `flows/work_item_handler.py`
 - **Purpose**: Abstract base class for all work item handlers
 - **Features**: Template method pattern with common workflow steps

#### 3. GlassWorkItemStrategy Implementation ✅
  - Placeholder mappings for damage types and locations (requires UI text capture)
  - Complaint detection logic for glass-related keywords
  - Structured methods for new/existing complaint scenarios
#### 3. GlassWorkItemHandler Implementation ✅
 - **File**: `flows/work_item_handler.py`
 - **Purpose**: Concrete handler for glass work items
 - **Features**: 
   - Placeholder mappings for damage types and locations (requires UI text capture)
   - Complaint detection logic for glass-related keywords
   - Structured methods for new/existing complaint scenarios

#### 4. Strategy Factory ✅
#### 4. Handler Factory ✅
 - **File**: `flows/work_item_handler.py`
 - **Function**: `create_work_item_handler()`
 - **Purpose**: Creates appropriate handler based on work item type

#### 5. Updated CSV Reading ✅
**Location**: Update `GlassWorkItemHandler.DAMAGE_TYPE_MAPPINGS` and `LOCATION_MAPPINGS`
- **File**: `GlassDamageWorkItemScript.py`
- **Function**: `read_mva_list()` 
- **Features**: Returns WorkItemConfig objects instead of MVA strings

#### 6. Updated Main Script Loop ✅
- **File**: `GlassDamageWorkItemScript.py`
- **Features**: Uses WorkItemConfig objects and strategy pattern

#### 7. Strategy Integration ✅
- **File**: `flows/work_item_flow.py`
- **Function**: `create_work_item_with_strategy()`
- **Purpose**: Entry point for strategy-based work item creation

## NEXT PHASE: UI Text Mapping & Workflow Implementation

### Required Tasks:

#### 1. Capture Exact UI Text Mappings 🔄
**Location**: Update `GlassWorkItemStrategy.DAMAGE_TYPE_MAPPINGS` and `LOCATION_MAPPINGS`

**Current Placeholders to Replace**:
```python
DAMAGE_TYPE_MAPPINGS = {
    "REPLACEMENT": "Replace",  # TODO: Capture exact UI text
    "CRACK": "Crack",         # TODO: Capture exact UI text  
    "CHIP": "Chip"            # TODO: Capture exact UI text
}

LOCATION_MAPPINGS = {
    "WINDSHIELD": "Windshield",  # TODO: Capture exact UI text
    "REAR": "Rear",              # TODO: Capture exact UI text
    "SIDE": "Side"               # TODO: Capture exact UI text
}
```

**Action Required**: Manual iteration through glass workflow to capture exact button/option text

#### 2. Implement New Complaint Creation Logic 📋
**Method**: `GlassWorkItemHandler.create_new_complaint()`

**Scenario**: Glass replacement with no existing complaint
**Steps to Implement**:
```
1. Click: Add Work Item Btn ✅ (implemented in base class)
2. Prompt: Is vehicle drivable? (click No btn) 🔄
3. Select issue type btn (click "Glass Damage" btn) 🔄 
4. Damage Type (click btn based on CSV using DAMAGE_TYPE_MAPPINGS) 🔄
5. Click Submit Complaint btn 🔄
```

#### 3. Implement Existing Complaint Handling 📋
**Method**: `GlassWorkItemHandler.handle_existing_complaint()`

**Scenario 1**: Glass repair with existing complaint
**Steps to Implement**:
```
1. Select existing complaint button "...Windshield Chip" 🔄
2. Click Next 🔄
3. Recorded Mileage - Click Next 🔄
4. Select OpCode - "Glass Repair/Replace" 🔄
5. Click "Done" btn 🔄
```

**Scenario 2**: Glass replacement with existing complaint  
**Steps to Implement**:
```
1. Select existing complaint button "Glass Damage..." 🔄
2. Select workitem type (Replace) 🔄
3. Recorded Mileage - Click Next 🔄
4. Select OpCode - "Glass Repair/Replace" 🔄
5. Click "Done" btn 🔄
```

#### 4. Enhanced Complaint Detection 📋
**Method**: `GlassWorkItemHandler.should_handle_existing_complaint()`

**Current Implementation**: Basic keyword matching
**Enhancement Needed**: More sophisticated detection to distinguish between:
- Windshield Chip complaints
- Glass Damage complaints  
- Other glass-related complaints

#### 5. OpCode Integration 📋
**Integration Point**: Both complaint scenarios end with OpCode selection
**Requirement**: Map to exact UI text for "Glass Repair/Replace" option

## Technical Architecture Benefits ✅

### 1. Extensibility
- Easy to add new work item types (PM, Brake, etc.)
- Each type gets its own strategy class
- Shared common logic in base class

### 2. Maintainability  
- Clear separation of concerns
- Type-specific logic isolated in strategy classes
- Common workflow steps centralized

### 3. Testability
- Strategy classes can be unit tested independently
- Mock strategies possible for testing
- Clear interfaces and contracts

### 4. Backward Compatibility
- Original `create_new_workitem()` function preserved
- Existing scripts continue to work
- Gradual migration path available

## File Structure
```
flows/
├── work_item_handler.py    # Handler pattern implementation
├── work_item_flow.py        # Integration with existing flows
├── complaints_flows.py      # Complaint handling (existing)
└── finalize_flow.py         # Work item finalization (existing)

GlassDamageWorkItemScript.py # Updated main script
data/
└── GlassWorkItems.csv       # Glass-specific CSV structure
```

## Testing Strategy
1. **Unit Tests**: Test each strategy method independently
2. **Integration Tests**: Test full workflow with mock UI interactions
3. **UI Tests**: Test with actual Compass UI using test MVAs
4. **Regression Tests**: Ensure existing PM functionality unaffected

## Future Expansion Template
Adding new work item types follows this pattern:
1. Create `{Type}WorkItemHandler` class extending `WorkItemHandler`
2. Implement abstract methods with type-specific logic
3. Add strategy to factory function
4. Create type-specific CSV structure
5. Create/update type-specific script
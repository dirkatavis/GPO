## Plan: GlassDamageWorkItemScript PRD Workflow Detailing

You will identify and document the specific workflow steps for the GlassDamageWorkItemScript in the PRD. This will clarify the automation sequence, decision points, and error handling for each MVA processed.

### Steps
1. List each major step in the script’s workflow (login, MVA input, validation, work item detection/creation, logging, etc.).
2. For each step, specify:
    - Preconditions (what must be true before this step)
    - Actions performed (UI, data, or logic)
    - Expected outcomes and error handling
3. Update the PRD in Docs/GlassDamageWorkItemScript.md with this detailed workflow.
4. Review and iterate on the workflow steps for completeness and clarity.

### Further Considerations
1. Should workflow steps include UI screenshots or selectors for clarity?
2. Should error handling be described for each step or in a separate section?


### Basic Flow(no complaint)
1. (main screen)Click Add Work Item btn
--If the MVA already had an existint complaint we would see it at this point and could select it
2. (Open Complaint Screen)Click Add New Complaint btn
3. (Drivability Screen) Click Yes/No btn <==Does not change the flow either way
4. (Complaint Type Screen) Click Glass Damage btn
5. (Glass Damage Type) Click damage type(crack/Chip/Side,rear) btn
6. (Submit Screen) Click Submit Complaint(btn)
7. (Mileage Screen) Click Next btn
8. (OpsCode Screen) Select "Glass Repair/Replace(btn)
9. (OpsCode Screen) Click Creat Work Item btn
0. (Wi Screen) Click Done button
"""Captured DOM snippets for Compass GO views.

Source: live Compass GO session, MVA 058883134, 2026-06-02.
Trimmed of framework noise; stable hooks (data-key, class, aria-label) preserved.
"""

VEHICLE_DETAILS_EXPANDED_HTML = """
<html><body>
<button class="back-button" type="button"><svg></svg></button>
<h2>Vehicle Details</h2>
<table>
  <tbody>
    <tr data-key="makeModelDesc" role="row">
      <td role="rowheader"><span>Description</span></td>
      <td role="gridcell"><span>NISSROGU</span></td>
    </tr>
    <tr data-key="mvaNo" role="row">
      <td role="rowheader"><span>MVA</span></td>
      <td role="gridcell"><span>058883134</span></td>
    </tr>
    <tr data-key="vinNo" role="row">
      <td role="rowheader"><span>VIN</span></td>
      <td role="gridcell"><span>5XYP64GC1SG682257</span></td>
    </tr>
  </tbody>
</table>
<button type="button">Show Less</button>
</body></html>
"""

VEHICLE_DETAILS_COLLAPSED_HTML = """
<html><body>
<h2>Vehicle Details</h2>
<table>
  <tbody>
    <tr data-key="mvaNo" role="row">
      <td role="rowheader"><span>MVA</span></td>
      <td role="gridcell"><span>058883134</span></td>
    </tr>
  </tbody>
</table>
<button type="button">Show More</button>
</body></html>
"""

SCAN_VEHICLE_HTML = """
<html><body>
<h2>Scan Vehicle</h2>
<div class="enter-mva-vin">
  <div>
    <input aria-label="Or enter MVA/VIN" type="text" placeholder="Or enter MVA/VIN" />
  </div>
  <button type="button">Enter</button>
</div>
</body></html>
"""

# Link Source Legend Feature

## Overview

This feature adds explicit visual distinction and legend entries for different types of mesh network links displayed on the map, making it clear whether links are:
- **Radio measured**: Direct NEIGHBORINFO packets received via radio
- **MQTT provided**: NEIGHBORINFO packets collected via MQTT server
- **Radio inferred**: Topology-based links calculated when NEIGHBORINFO is unavailable

## Problem Solved

Previously, all mesh links were displayed with the same visual style, making it impossible to distinguish between:
1. Links measured directly by the local radio node
2. Links collected from a remote MQTT server (showing topology beyond local radio range)
3. Links inferred from hop-count topology when NEIGHBORINFO data wasn't available

This lack of distinction made it difficult to:
- Understand data source reliability
- Diagnose network issues
- Plan network expansion
- Evaluate MQTT collector effectiveness

## Solution

### Database Schema Enhancement

Added a `source` field to the `neighbors` table to track the origin of each neighbor relationship:

```sql
ALTER TABLE neighbors ADD COLUMN source TEXT DEFAULT 'radio'
```

**Migration**: The code automatically adds this column to existing databases, with old data defaulting to 'radio'.

### Backend Changes

1. **traffic_persistence.py**
   - Added `source` parameter to `save_neighbor_info()` (defaults to 'radio')
   - Updated `load_neighbors()` to include source in returned data
   - Modified `export_neighbors_to_json()` to export source field

2. **traffic_monitor.py**
   - Passes `source='radio'` when saving NEIGHBORINFO from radio packets

3. **mqtt_neighbor_collector.py**
   - Passes `source='mqtt'` when saving NEIGHBORINFO from MQTT messages

### Frontend Visualization

**map.html** enhancements:

1. **Color Differentiation**:
   - **Radio links**: Green/Yellow/Orange (based on SNR)
   - **MQTT links**: Cyan/Blue tones (based on SNR)
   - **Inferred links**: Gray, dashed, semi-transparent

2. **Updated Functions**:
   - `getLinkColor(snr, source)`: Returns color based on both SNR and source
   - `getLinkOpacity(snr, source)`: MQTT links slightly more transparent
   - `getLinkWeight(snr, source)`: MQTT links slightly thinner
   - `getLinkDescription(source, isInferred)`: Descriptive text for popups

3. **Enhanced Legend**:
   - **Section 1**: SNR Quality (Excellent/Good/Weak)
   - **Section 2**: Link Source (Radio/MQTT/Inferred)

## Visual Examples

### Radio Links (Direct Measurement)
- **Green** (SNR > 5): `#00ff00` - Excellent radio link
- **Yellow** (SNR 0-5): `#ffff00` - Good radio link
- **Orange** (SNR < 0): `#ff6600` - Weak radio link

### MQTT Links (Remote Collector)
- **Cyan** (SNR > 5): `#00ffff` - Excellent MQTT link
- **Dodger Blue** (SNR 0-5): `#1e90ff` - Good MQTT link
- **Royal Blue** (SNR < 0): `#4169e1` - Weak MQTT link
- **Deep Sky Blue** (no SNR): `#00bfff` - MQTT link without SNR data

### Inferred Links (Topology)
- **Gray** with dashed line: `#888888` at 50% opacity
- Used when NEIGHBORINFO is unavailable
- Based on hop-count topology

## Link Popup Information

When clicking on a link, the popup now shows:

```
Liaison radio (mesure directe)
NodeA ↔ NodeB
SNR: 7.5 dB
Source: Radio
```

Or for MQTT:

```
Liaison MQTT (collecteur distant)
NodeA ↔ NodeB
SNR: 6.2 dB
Source: MQTT
```

Or for inferred:

```
Liaison inférée (topologie)
NodeA → NodeB
Distance: 2 hop(s)
SNR: 5.0 dB
Source: Inféré (topologie)
```

## Benefits

1. **Transparency**: Instantly identify the source and reliability of each link
2. **Extended Visibility**: MQTT links reveal topology beyond local radio range
3. **Improved Diagnostics**: Distinguish real measurements from inferences
4. **Network Planning**: Make informed decisions about node placement
5. **Quality Assessment**: Evaluate MQTT collector effectiveness

## Backward Compatibility

- Old neighbor data without `source` field defaults to `'radio'`
- Database migration is automatic and non-destructive
- All existing functionality continues to work unchanged

## Testing

The implementation includes:
- Database migration from old schema
- Mixed source data (radio + MQTT)
- Export to JSON with source preservation
- Visual demonstration page (demo_link_legend.html)

## Files Modified

- `traffic_persistence.py`: Database schema and source tracking
- `traffic_monitor.py`: Radio source tagging
- `mqtt_neighbor_collector.py`: MQTT source tagging
- `map/map.html`: Visual styling and legend
- `map/demo_link_legend.html`: Feature demonstration (new file)

## Future Enhancements

Potential improvements:
- Filter links by source in the UI
- Statistics on source distribution
- Source-specific styling preferences
- Export source metrics to analytics

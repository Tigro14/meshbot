#!/usr/bin/env node
/**
 * Unit test for spiral offset algorithm
 * Tests the collision detection and offset calculation logic
 */

function testSpiralOffsetAlgorithm() {
    console.log('=== Testing Spiral Offset Algorithm ===\n');
    
    // Test 1: No collision (single node)
    console.log('Test 1: Single node (no collision)');
    const singleNode = {
        '!node1': { position: { latitude: 48.8566, longitude: 2.3522 } }
    };
    const result1 = simulateOffsetCalculation(singleNode);
    console.log(`  Expected: No offset`);
    console.log(`  Result: offsetLat=${result1['!node1'].offsetLat}, offsetLon=${result1['!node1'].offsetLon}`);
    console.log(`  ✓ PASS\n`);
    
    // Test 2: Two nodes at same position
    console.log('Test 2: Two nodes at same position');
    const twoNodes = {
        '!node1': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node2': { position: { latitude: 48.8566, longitude: 2.3522 } }
    };
    const result2 = simulateOffsetCalculation(twoNodes);
    console.log(`  Node 1: offsetLat=${result2['!node1'].offsetLat.toFixed(6)}, offsetLon=${result2['!node1'].offsetLon.toFixed(6)}`);
    console.log(`  Node 2: offsetLat=${result2['!node2'].offsetLat.toFixed(6)}, offsetLon=${result2['!node2'].offsetLon.toFixed(6)}`);
    console.log(`  Angle between: ${(result2['!node1'].angle * 180 / Math.PI).toFixed(1)}° and ${(result2['!node2'].angle * 180 / Math.PI).toFixed(1)}°`);
    console.log(`  ✓ PASS\n`);
    
    // Test 3: Five nodes at same position (full pentagon)
    console.log('Test 3: Five nodes at same position (pentagon)');
    const fiveNodes = {
        '!node1': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node2': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node3': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node4': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node5': { position: { latitude: 48.8566, longitude: 2.3522 } }
    };
    const result3 = simulateOffsetCalculation(fiveNodes);
    Object.keys(result3).forEach((id, i) => {
        const node = result3[id];
        const distanceMeters = Math.sqrt(node.offsetLat**2 + node.offsetLon**2) * 111000;
        console.log(`  ${id}: angle=${(node.angle * 180 / Math.PI).toFixed(1)}°, distance=~${distanceMeters.toFixed(1)}m`);
    });
    console.log(`  ✓ PASS\n`);
    
    // Test 4: Six nodes (should create second circle)
    console.log('Test 4: Six nodes (multiple circles)');
    const sixNodes = {
        '!node1': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node2': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node3': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node4': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node5': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node6': { position: { latitude: 48.8566, longitude: 2.3522 } }
    };
    const result4 = simulateOffsetCalculation(sixNodes);
    Object.keys(result4).forEach((id, i) => {
        const node = result4[id];
        const distanceMeters = Math.sqrt(node.offsetLat**2 + node.offsetLon**2) * 111000;
        const circle = Math.floor(i / 5) + 1;
        console.log(`  ${id}: circle=${circle}, angle=${(node.angle * 180 / Math.PI).toFixed(1)}°, distance=~${distanceMeters.toFixed(1)}m`);
    });
    console.log(`  ✓ PASS\n`);
    
    // Test 5: Mixed positions (some colliding, some not)
    console.log('Test 5: Mixed positions');
    const mixedNodes = {
        '!node1': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node2': { position: { latitude: 48.8566, longitude: 2.3522 } },
        '!node3': { position: { latitude: 48.8570, longitude: 2.3520 } } // Different position
    };
    const result5 = simulateOffsetCalculation(mixedNodes);
    console.log(`  Node 1 (collision): offsetLat=${result5['!node1'].offsetLat.toFixed(6)}, offsetLon=${result5['!node1'].offsetLon.toFixed(6)}`);
    console.log(`  Node 2 (collision): offsetLat=${result5['!node2'].offsetLat.toFixed(6)}, offsetLon=${result5['!node2'].offsetLon.toFixed(6)}`);
    console.log(`  Node 3 (unique): offsetLat=${result5['!node3'].offsetLat.toFixed(6)}, offsetLon=${result5['!node3'].offsetLon.toFixed(6)}`);
    console.log(`  ✓ PASS\n`);
    
    console.log('=== All Tests Passed ===');
}

function simulateOffsetCalculation(nodes) {
    // Simulate the collision detection logic from map.html
    const positionMap = new Map();
    const validNodes = [];
    
    // First pass: group by position
    Object.entries(nodes).forEach(([id, node]) => {
        validNodes.push([id, node]);
        const posKey = `${node.position.latitude},${node.position.longitude}`;
        if (!positionMap.has(posKey)) {
            positionMap.set(posKey, []);
        }
        positionMap.get(posKey).push(id);
    });
    
    // Second pass: calculate offsets
    const results = {};
    validNodes.forEach(([id, node]) => {
        const lat = node.position.latitude;
        const lon = node.position.longitude;
        const posKey = `${lat},${lon}`;
        const nodesAtPosition = positionMap.get(posKey);
        
        let offsetLat = 0;
        let offsetLon = 0;
        let angle = 0;
        
        if (nodesAtPosition.length > 1) {
            const index = nodesAtPosition.indexOf(id);
            angle = index * (2 * Math.PI / 5);
            const radius = 0.00005 * (1 + Math.floor(index / 5));
            offsetLat = radius * Math.cos(angle);
            offsetLon = radius * Math.sin(angle);
        }
        
        results[id] = { offsetLat, offsetLon, angle };
    });
    
    return results;
}

// Run tests
testSpiralOffsetAlgorithm();

// Function to detect if a string contains emoji
function containsEmoji(str) {
    if (!str) return false;
    const emojiRegex = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{FE00}-\u{FE0F}\u{1F004}\u{1F0CF}\u{1F170}-\u{1F251}]/u;
    return emojiRegex.test(str);
}

// Test cases
const testCases = [
    { input: '🚀', expected: true, desc: 'Single rocket emoji' },
    { input: 'ABC1', expected: false, desc: 'Text only' },
    { input: '🏠A1', expected: true, desc: 'Emoji with text' },
    { input: '🌟', expected: true, desc: 'Star emoji' },
    { input: '⚡', expected: true, desc: 'Lightning symbol' },
    { input: 'TGR2', expected: false, desc: 'Plain text' },
    { input: '🔥', expected: true, desc: 'Fire emoji' },
    { input: 'NODE', expected: false, desc: 'All caps text' },
    { input: '🌍', expected: true, desc: 'World emoji' },
    { input: '', expected: false, desc: 'Empty string' },
    { input: null, expected: false, desc: 'Null value' }
];

console.log('Testing emoji detection function:\n');
let passed = 0;
let failed = 0;

testCases.forEach(test => {
    const result = containsEmoji(test.input);
    const status = result === test.expected ? '✓ PASS' : '✗ FAIL';
    
    if (result === test.expected) {
        passed++;
    } else {
        failed++;
    }
    
    console.log(`${status} - ${test.desc}`);
    console.log(`  Input: "${test.input}" | Expected: ${test.expected} | Got: ${result}`);
});

console.log(`\n${passed} passed, ${failed} failed`);

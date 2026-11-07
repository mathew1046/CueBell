import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

// Extract static UI copy, state labels and service errors. No user data is read.
const messages = new Set(['no token', '{type} · {token}', '{label}, {token}', '{mode} theme']);
function walk(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) { if (entry.name !== 'i18n') walk(file); continue; }
    if (!/\.tsx?$/.test(file)) continue;
    const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
    function visit(node) {
      if (ts.isCallExpression(node) && node.expression.getText(source) === 't' && node.arguments[0] && ts.isStringLiteral(node.arguments[0])) messages.add(node.arguments[0].text);
      if (ts.isStringLiteral(node) && (/^[A-Z][a-z]/.test(node.text) || /^\{\w+\}/.test(node.text))) {
        if (!/Provider is missing|HTTPS.*required/.test(node.text)) messages.add(node.text);
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
}
walk('src');
for (const file of fs.readdirSync('modules/queue-listener/android/src/main/java/expo/modules/queuelistener')) {
  if (!/\.kt$/.test(file)) continue;
  const content = fs.readFileSync(`modules/queue-listener/android/src/main/java/expo/modules/queuelistener/${file}`, 'utf8');
  for (const match of content.matchAll(/"((?:[^"\\]|\\.)*)"/g)) {
    const text = match[1];
    if (/^[A-Z][a-z]/.test(text) && text.includes(' ') && !text.includes('$') && !text.includes('\\') && !text.includes(':')) messages.add(text);
  }
}
// Shared backend validation messages are protocol values, localized only at display time.
for (const text of [
  'The target must be grounded in your request.',
  'What should I listen for, and when should I alert you?',
  'The event must be grounded in your request. Please describe it again.',
  'Describe an event I can hear in speech and alert you about.',
  'Which token should I monitor?', 'Specify visual, vibration, or sound alerts.',
  'Stop or pause the microphone before editing your request.', 'Monitor changed. Submit the request again.',
  'Pause listening before changing the monitor.', 'Proposal expired. Submit the request again.',
  'Called', 'Correction', 'Cancelled', 'Other', 'Uncertain', 'Event detected',
  'Token calls', 'A call may have been missed. Open the app and reconnect.',
]) messages.add(text);
for (const unused of ['Content-Type', 'QueueListener', 'Could not update or remove the saved session. Retry Stop before closing the app, ']) messages.delete(unused);
const result = Object.fromEntries([...messages].sort().map(message => [message, message]));
fs.writeFileSync('src/lib/i18n/en.json', JSON.stringify(result, null, 2) + '\n');
console.log(`Extracted ${messages.size} source messages.`);

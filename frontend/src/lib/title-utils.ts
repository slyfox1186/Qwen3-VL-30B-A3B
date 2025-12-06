/**
 * Generate a title from a message content.
 * Cleans and truncates the message to create a suitable title.
 */
export function generateTitleFromMessage(message: string): string {
  // Remove excessive whitespace and normalize
  const normalized = message.trim().replace(/\s+/g, ' ');

  if (!normalized) {
    return 'New conversation';
  }

  const maxLength = 40;

  if (normalized.length <= maxLength) {
    return normalized;
  }

  // Truncate at word boundary if possible
  const truncated = normalized.substring(0, maxLength);
  const lastSpace = truncated.lastIndexOf(' ');

  // Only break at word if we're past 60% of max length
  if (lastSpace > maxLength * 0.6) {
    return truncated.substring(0, lastSpace) + '...';
  }

  return truncated + '...';
}

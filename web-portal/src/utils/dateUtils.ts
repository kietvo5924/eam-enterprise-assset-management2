export const formatToTenantTimezone = (utcString: string, timezone: string): string => {
  try {
    const date = new Date(utcString);
    return new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    }).format(date);
  } catch (error) {
    return utcString;
  }
};

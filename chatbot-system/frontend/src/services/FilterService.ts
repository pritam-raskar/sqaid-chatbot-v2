/**
 * Filter Service
 * Manages filters for parent-child communication
 */

export interface Filter {
  field: string;
  operator: 'equals' | 'contains' | 'greaterThan' | 'lessThan' | 'in' | 'between';
  value: any;
}

export interface FilterSet {
  filters: Filter[];
  logic: 'AND' | 'OR';
}

export class FilterService {
  private activeFilters: Map<string, Filter>;

  constructor() {
    this.activeFilters = new Map();
  }

  /**
   * Add or update a filter
   */
  setFilter(field: string, operator: Filter['operator'], value: any): void {
    this.activeFilters.set(field, {
      field,
      operator,
      value
    });
  }

  /**
   * Remove a filter
   */
  removeFilter(field: string): boolean {
    return this.activeFilters.delete(field);
  }

  /**
   * Clear all filters
   */
  clearFilters(): void {
    this.activeFilters.clear();
  }

  /**
   * Get all active filters
   */
  getFilters(): Filter[] {
    return Array.from(this.activeFilters.values());
  }

  /**
   * Get filter by field
   */
  getFilter(field: string): Filter | undefined {
    return this.activeFilters.get(field);
  }

  /**
   * Check if field has filter
   */
  hasFilter(field: string): boolean {
    return this.activeFilters.has(field);
  }

  /**
   * Convert filters to query parameters
   */
  toQueryParams(): Record<string, string> {
    const params: Record<string, string> = {};

    this.activeFilters.forEach((filter, field) => {
      switch (filter.operator) {
        case 'equals':
          params[field] = String(filter.value);
          break;
        case 'contains':
          params[`${field}_contains`] = String(filter.value);
          break;
        case 'greaterThan':
          params[`${field}_gt`] = String(filter.value);
          break;
        case 'lessThan':
          params[`${field}_lt`] = String(filter.value);
          break;
        case 'in':
          params[field] = Array.isArray(filter.value)
            ? filter.value.join(',')
            : String(filter.value);
          break;
        case 'between':
          if (Array.isArray(filter.value) && filter.value.length === 2) {
            params[`${field}_gte`] = String(filter.value[0]);
            params[`${field}_lte`] = String(filter.value[1]);
          }
          break;
      }
    });

    return params;
  }

  /**
   * Convert filters to filter set
   */
  toFilterSet(logic: 'AND' | 'OR' = 'AND'): FilterSet {
    return {
      filters: this.getFilters(),
      logic
    };
  }

  /**
   * Apply filters from filter set
   */
  fromFilterSet(filterSet: FilterSet): void {
    this.clearFilters();
    filterSet.filters.forEach(filter => {
      this.setFilter(filter.field, filter.operator, filter.value);
    });
  }

  /**
   * Merge filters from another set
   */
  merge(filters: Filter[]): void {
    filters.forEach(filter => {
      this.setFilter(filter.field, filter.operator, filter.value);
    });
  }

  /**
   * Get filter count
   */
  count(): number {
    return this.activeFilters.size;
  }

  /**
   * Check if any filters are active
   */
  hasFilters(): boolean {
    return this.activeFilters.size > 0;
  }

  /**
   * Get filter summary for display
   */
  getSummary(): string {
    if (this.activeFilters.size === 0) {
      return 'No filters applied';
    }

    const summaries = Array.from(this.activeFilters.values()).map(filter => {
      const operatorText = {
        equals: '=',
        contains: 'contains',
        greaterThan: '>',
        lessThan: '<',
        in: 'in',
        between: 'between'
      }[filter.operator];

      return `${filter.field} ${operatorText} ${filter.value}`;
    });

    return summaries.join(', ');
  }

  /**
   * Clone filters
   */
  clone(): FilterService {
    const cloned = new FilterService();
    this.activeFilters.forEach((filter, field) => {
      cloned.setFilter(field, filter.operator, filter.value);
    });
    return cloned;
  }

  /**
   * Export filters as JSON
   */
  toJSON(): string {
    return JSON.stringify(this.toFilterSet());
  }

  /**
   * Import filters from JSON
   */
  fromJSON(json: string): void {
    try {
      const filterSet = JSON.parse(json) as FilterSet;
      this.fromFilterSet(filterSet);
    } catch (error) {
      console.error('Failed to parse filter JSON:', error);
    }
  }
}

// Singleton instance
export const filterService = new FilterService();

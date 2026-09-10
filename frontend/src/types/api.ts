export type CyclingProfile = "road" | "commuter" | "leisure";

export type Coordinate = {
  lat: number;
  lon: number;
};

export type RoutePreferences = {
  distanceWeight: number;
  bikeabilityWeight: number;
};

export type RouteConstraints = {
  minDistanceM?: number;
  maxDistanceM?: number;
  maxBadRoadFraction?: number;
  maxHighSpeedFraction?: number;
  maxElevationGainM?: number;
};

export type GeoJsonLineString = {
  type: "LineString";
  coordinates: [number, number][];
};

export type RouteProfileSample = {
  distanceM: number;
  elevationM: number | null;
  bikeability: number;
};

export type RouteScoreBreakdown = {
  averageBikeability: number;
  highQualityBonus: number;
  badRoadPenalty: number;
  intersectionPenalty: number;
  distancePenalty: number;
};

export type OptimizationMetadata = {
  algorithmVersion: string;
  candidatesEvaluated?: number;
  candidatesRejected?: number;
};

export type RouteResponse = {
  routeId: string;
  geometry: GeoJsonLineString;
  distanceM: number;
  elevationGainM: number;
  averageBikeability: number;
  pctHighQuality: number;
  pctBadRoads: number;
  pctProtected: number;
  highSpeedExposure: number;
  hostileIntersections: number;
  score: number;
  profile: RouteProfileSample[];
  scoreBreakdown?: RouteScoreBreakdown;
  optimization?: OptimizationMetadata;
};

export type SegmentRouteResponse = {
  geometry: GeoJsonLineString;
  distanceM: number;
  averageBikeability: number;
  elevationGainM: number;
};

export type SegmentRouteRequest = {
  start: Coordinate;
  end: Coordinate;
  profile: CyclingProfile;
  preferences: RoutePreferences;
};

export type ManualRouteRequest = {
  waypoints: Coordinate[];
  profile: CyclingProfile;
  preferences: RoutePreferences;
};

export type LoopRouteRequest = {
  start: Coordinate;
  targetDistanceM: number;
  profile: CyclingProfile;
  preferences: RoutePreferences;
  constraints?: RouteConstraints;
};

export type HealthResponse = {
  status: string;
};

export type BBox = {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
};

export type CitySummary = {
  cityId: string;
  name: string;
  bbox: BBox;
  graphVersion: string;
  scoreVersion: string;
};

export type CityListResponse = {
  cities: CitySummary[];
};

export type BikeabilityFeature = {
  type: "Feature";
  properties: {
    roadId: string;
    bikeability: number;
  };
  geometry: GeoJsonLineString;
};

export type BikeabilityNetworkResponse = {
  cityId: string;
  scoreVersion: string;
  features: BikeabilityFeature[];
};

export type RoadInspectionResponse = {
  roadId: string;
  geometry: GeoJsonLineString;
  features: {
    highway?: string | null;
    speedKph?: number | null;
    lanes?: number | null;
    surface?: string | null;
    protectedBikeInfrastructure: boolean;
    bikeLane: boolean;
    grade?: number | null;
  };
  bikeability: {
    score: number;
    components: {
      infrastructure: number;
      roadComfort: number;
      speed: number;
      traffic: number;
      surface: number;
      grade: number;
    };
  };
  profile: CyclingProfile;
};

export type ApiErrorCode =
  | "INVALID_REQUEST"
  | "INVALID_COORDINATES"
  | "CITY_NOT_AVAILABLE"
  | "ROUTE_NOT_FOUND"
  | "DISTANCE_CONSTRAINT_UNSATISFIABLE"
  | "GRAPH_UNAVAILABLE"
  | "ROUTE_GENERATION_FAILED"
  | "INTERNAL_ERROR";

export type ApiErrorBody = {
  code: ApiErrorCode;
  message: string;
  details: Record<string, unknown>;
};

export type ApiErrorEnvelope = {
  error: ApiErrorBody;
};

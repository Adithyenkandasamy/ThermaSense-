export type FacilityApiStatus = {
  status: "not_implemented";
};

export async function listFacilities(): Promise<FacilityApiStatus> {
  return { status: "not_implemented" };
}

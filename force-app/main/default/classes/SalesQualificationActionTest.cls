@IsTest
private class SalesQualificationActionTest {
  @IsTest
  static void hotOnVpDemo() {
    SalesQualificationAction.Request r = new SalesQualificationAction.Request();
    r.title = 'VP Sales';
    r.companySize = 'Enterprise 2000 staff';
    r.intent = 'Wants demo and pricing';
    List<SalesQualificationAction.Result> res = SalesQualificationAction.scoreLeads(new List<SalesQualificationAction.Request>{ r });
    System.assertEquals(1, res.size());
    System.assertEquals('Hot', res[0].tier);
  }
  @IsTest
  static void bulkSafe() {
    List<SalesQualificationAction.Request> items = new List<SalesQualificationAction.Request>();
    for (Integer i = 0; i < 10; i++) {
      SalesQualificationAction.Request r = new SalesQualificationAction.Request();
      r.title = 'Manager';
      r.companySize = 'SMB';
      r.intent = 'Just browsing';
      items.add(r);
    }
    List<SalesQualificationAction.Result> res = SalesQualificationAction.scoreLeads(items);
    System.assertEquals(10, res.size());
  }
}

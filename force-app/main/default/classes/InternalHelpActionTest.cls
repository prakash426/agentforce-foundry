@IsTest
private class InternalHelpActionTest {
  @IsTest
  static void selfServeOnVpn() {
    InternalHelpAction.Request r = new InternalHelpAction.Request();
    r.question = 'VPN keeps dropping';
    r.urgency = 'low';
    List<InternalHelpAction.Result> res = InternalHelpAction.answerIt(new List<InternalHelpAction.Request>{ r });
    System.assertEquals(1, res.size());
    System.assertEquals(false, res[0].openTicket);
    System.assertEquals('Self_Serve', res[0].queue);
  }
  @IsTest
  static void bulkSafe() {
    List<InternalHelpAction.Request> items = new List<InternalHelpAction.Request>();
    for (Integer i = 0; i < 10; i++) {
      InternalHelpAction.Request r = new InternalHelpAction.Request();
      r.question = 'Laptop crash ' + i;
      r.urgency = 'urgent';
      items.add(r);
    }
    List<InternalHelpAction.Result> res = InternalHelpAction.answerIt(items);
    System.assertEquals(10, res.size());
  }
}

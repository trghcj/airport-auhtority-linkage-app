library default_connector;
import 'package:cloud_firestore/cloud_firestore.dart';
import 'dart:convert';



class DefaultConnector {
  

  static ConnectorConfig connectorConfig = ConnectorConfig(
    'us-central1',
    'default',
    'airportauhtoritylinkageapp',
  );

  DefaultConnector({required this.dataConnect});
  static DefaultConnector get instance {
    return DefaultConnector(
        dataConnect: FirebaseDataConnect.instanceFor(
            connectorConfig: connectorConfig,
            sdkType: CallerSDKType.generated));
  }

  FirebaseDataConnect dataConnect;
}

class FirebaseDataConnect {
  static instanceFor({required ConnectorConfig connectorConfig, required sdkType}) {}
}

class CallerSDKType {
  // ignore: prefer_typing_uninitialized_variables
  static var generated;
}

class ConnectorConfig {
  ConnectorConfig(String s, String t, String u);
}


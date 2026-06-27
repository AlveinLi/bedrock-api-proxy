import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import { Construct } from 'constructs';
import { EnvironmentConfig } from '../config/config';

export interface DatabaseStackProps extends cdk.StackProps {
  config: EnvironmentConfig;
  vpc: ec2.IVpc;
  // ECS task security group; allowed inbound to MySQL (3306).
  ecsSecurityGroup: ec2.ISecurityGroup;
}

/**
 * RDS for MySQL — persistence layer for usage detail, content audit, and the
 * API key master store. Only created when config.mysqlEnabled is true, so the
 * stack has zero footprint for environments that do not use MySQL.
 */
export class DatabaseStack extends cdk.Stack {
  public readonly instance: rds.DatabaseInstance;
  public readonly securityGroup: ec2.SecurityGroup;
  public readonly databaseName: string;

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {
    super(scope, id, props);

    const { config, vpc, ecsSecurityGroup } = props;
    const isProd = config.environmentName === 'prod';
    this.databaseName = config.mysqlDatabase;

    // Security group for the database; only ECS tasks may reach 3306.
    this.securityGroup = new ec2.SecurityGroup(this, 'DatabaseSecurityGroup', {
      vpc,
      securityGroupName: `anthropic-proxy-${config.environmentName}-mysql-sg`,
      description: 'Security group for the Anthropic proxy MySQL database',
      allowAllOutbound: true,
    });

    this.securityGroup.addIngressRule(
      ecsSecurityGroup,
      ec2.Port.tcp(3306),
      'Allow MySQL access from ECS tasks'
    );

    // Plaintext master credentials from config (no Secrets Manager).
    const credentials = rds.Credentials.fromPassword(
      config.mysqlUser,
      cdk.SecretValue.unsafePlainText(config.mysqlPassword)
    );

    this.instance = new rds.DatabaseInstance(this, 'Database', {
      engine: rds.DatabaseInstanceEngine.mysql({
        version: rds.MysqlEngineVersion.VER_8_0,
      }),
      instanceType: new ec2.InstanceType(config.mysqlInstanceClass),
      vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      securityGroups: [this.securityGroup],
      credentials,
      databaseName: this.databaseName,
      allocatedStorage: config.mysqlAllocatedStorage,
      maxAllocatedStorage: config.mysqlAllocatedStorage * 4,
      storageType: rds.StorageType.GP3,
      multiAz: config.mysqlMultiAz,
      // utf8mb4 to match the application's content audit / unicode requirements.
      parameterGroup: new rds.ParameterGroup(this, 'DatabaseParameters', {
        engine: rds.DatabaseInstanceEngine.mysql({
          version: rds.MysqlEngineVersion.VER_8_0,
        }),
        parameters: {
          character_set_server: 'utf8mb4',
          collation_server: 'utf8mb4_unicode_ci',
        },
      }),
      backupRetention: cdk.Duration.days(isProd ? 14 : 1),
      deleteAutomatedBackups: !isProd,
      deletionProtection: isProd,
      removalPolicy: isProd ? cdk.RemovalPolicy.SNAPSHOT : cdk.RemovalPolicy.DESTROY,
      storageEncrypted: true,
      enablePerformanceInsights: isProd,
      cloudwatchLogsExports: ['error', 'slowquery'],
    });

    // Apply tags
    cdk.Tags.of(this).add('Environment', config.environmentName);
    Object.entries(config.tags).forEach(([key, value]) => {
      cdk.Tags.of(this).add(key, value);
    });

    new cdk.CfnOutput(this, 'DatabaseEndpoint', {
      value: this.instance.dbInstanceEndpointAddress,
      description: 'RDS MySQL endpoint address',
    });

    new cdk.CfnOutput(this, 'DatabaseName', {
      value: this.databaseName,
      description: 'MySQL database name',
    });
  }
}
